import argparse
import base64
import calendar
import io
import json
import logging
import sys
import traceback
import uuid
from datetime import datetime, timezone
from typing import Any, Generator, Optional

import psutil

from gen.intdash.v1.protocol_pb2 import (  # type: ignore
    StoreDataChunk,
    StoreDataChunks,
    StoreDataID,
    StoreDataPoint,
    StoreDataPointGroup,
)
from intdash import ApiClient, Configuration
from intdash.api import (
    measurement_service_measurement_base_times_api,
    measurement_service_measurement_markers_api,
    measurement_service_measurement_sequences_api,
    measurement_service_measurements_api,
)
from intdash.model.create_meas_base_time import CreateMeasBaseTime
from intdash.model.meas_base_time_name import MeasBaseTimeName
from intdash.model.meas_base_time_priority import MeasBaseTimePriority
from intdash.model.meas_create import MeasCreate
from intdash.model.measurement import Measurement
from intdash.model.measurement_base_time_type import MeasurementBaseTimeType
from intdash.model.measurement_marker_detail_point import MeasurementMarkerDetailPoint
from intdash.model.measurement_marker_detail_range import MeasurementMarkerDetailRange
from intdash.model.measurement_marker_post_request import MeasurementMarkerPostRequest
from intdash.model.measurement_sequence_group import MeasurementSequenceGroup
from intdash.model.measurement_sequence_group_replace import (
    MeasurementSequenceGroupReplace,
)

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# 定数定義
DEFAULT_MAX_POINTS_PER_REQUEST = 1000
DEFAULT_MAX_REQUEST_BYTES = 0


def measurement_decoder(dct: dict) -> dict:
    """
    計測デコーダー

    JSONオブジェクトをデコードする際に、特定のキーに対応する値を適切に変換する
    - basetime_typeの場合、対応するオブジェクトに変換
    - 日付文字列の場合、datetimeオブジェクトに変換
    - ナノ秒の情報を含む場合、適切にmicrosecondに変換

    Args:
        dct: デコード対象のJSONオブジェクト

    Returns:
        dict: 変換されたJSONオブジェクト
    """
    for key, value in dct.items():
        if isinstance(value, str):
            try:
                # basetime_typeの場合
                if key == "basetime_type":
                    dct[key] = MeasurementBaseTimeType(value)

                # datetimeの場合
                elif value.endswith("Z"):
                    dt = datetime.fromisoformat(value[:-1])
                    dt = dt.replace(tzinfo=timezone.utc)
                    dct[key] = dt
                elif "." in value:
                    dt = datetime.fromisoformat(value)
                    dct[key] = dt

                # ナノ秒の処理（.XXXXXXX000 の形式）
                if "." in value and isinstance(dct[key], datetime):
                    nano_part = value.split(".")[1][:9]
                    microseconds = int(nano_part[:6])
                    dt = dct[key].replace(microsecond=microseconds)
                    dct[key] = dt

            except ValueError:
                pass
    return dct


def log_memory_usage() -> None:
    """
    メモリ使用量出力
    """
    process = psutil.Process()
    mem_info = process.memory_info()
    logging.info(f"Memory Usage: {mem_info.rss / 1024 / 1024:.2f} MB")


def load(file_path: str) -> Generator[dict, None, None]:
    """
    JSON Linesファイル読み込み

    Args:
        file_path (str): JSON Linesファイルパス
    """
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                yield json.loads(line, object_hook=measurement_decoder)
            except json.JSONDecodeError as e:
                logging.warning(f"JSON decode error: {e}")


def to_api_body(model: Any) -> Any:
    """
    SDKのバージョン差分吸収

    intdash API Client のバージョンによって、APIに渡すBodyが
    pydantic modelそのものの場合とdictの場合があるため、to_dict()を
    持つモデルはdictに変換する。

    Args:
        model: APIに渡すリクエストBody

    Returns:
        Any: SDKバージョンに合わせて変換したリクエストBody
    """
    return model.to_dict() if hasattr(model, "to_dict") else model


def iter_api_items(response: Any) -> list:
    """
    SDKのバージョン差分吸収

    一覧レスポンスが response.items の場合と response["items"] の場合を吸収する。

    Args:
        response: APIの一覧レスポンス

    Returns:
        list: 一覧レスポンスのitems
    """
    if hasattr(response, "items") and not isinstance(response, dict):
        return response.items
    return response["items"]


def parse_basetime_ns(basetime: Any) -> int:
    """
    基準時刻をUnix epochナノ秒へ変換

    JSON Lines読み込み後のdatetime、および文字列の両方に対応する。

    Args:
        basetime: 基準時刻

    Returns:
        int: Unix epochナノ秒
    """
    if isinstance(basetime, datetime):
        dt = basetime
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return calendar.timegm(dt.utctimetuple()) * 1_000_000_000 + (
            dt.microsecond * 1_000
        )
    elif isinstance(basetime, str):
        value = basetime.replace("Z", "+00:00")
        if "." in value:
            prefix, suffix = value.split(".", 1)
            tz = ""
            for sep in ("+", "-"):
                if sep in suffix:
                    frac, tz_part = suffix.split(sep, 1)
                    tz = sep + tz_part
                    break
            else:
                frac = suffix
            ns = int(frac[:9].ljust(9, "0"))
            dt = datetime.fromisoformat(f"{prefix}.{frac[:6].ljust(6, '0')}{tz}")
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return calendar.timegm(dt.utctimetuple()) * 1_000_000_000 + ns
        dt = datetime.fromisoformat(value)
    else:
        raise TypeError(f"Unsupported basetime type: {type(basetime)}")

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return calendar.timegm(dt.utctimetuple()) * 1_000_000_000 + (
        dt.microsecond * 1_000
    )


def get_client(api_url: str, api_token: str) -> ApiClient:
    """
    REST APIクライアント生成

    Args:
        api_url: APIのURL
        api_token: APIトークン

    Returns:
        ApiClient: APIクライアント
    """
    configuration = Configuration(
        host=f"{api_url}/api", api_key={"IntdashToken": api_token}
    )
    client = ApiClient(configuration)
    return client


def create_measurement(
    client: ApiClient, project_uuid: str, edge_uuid: str, meas_src: dict
) -> Measurement:
    """
    計測作成

    Args:
        client: APIクライアント
        project_uuid: プロジェクトのUUID
        edge_uuid: エッジUUID
        meas_src: 計測情報

    Returns:
        Measurement: 作成された計測オブジェクト
    """
    meas_dist = meas_src.copy()
    meas_dist["edge_uuid"] = edge_uuid
    meas_create = MeasCreate(**meas_dist)
    api = measurement_service_measurements_api.MeasurementServiceMeasurementsApi(client)
    measurement = api.create_project_measurement(
        project_uuid, meas_create=to_api_body(meas_create)
    )
    logging.info(
        f"Created measurement: {measurement.uuid} edge_uuid {measurement.edge_uuid}"
    )
    return measurement


def clear_basetimes(
    client: ApiClient,
    project_uuid: str,
    measurement_uuid: str,
) -> None:
    """
    基準時刻クリア

    計測作成で作成した基準時刻を削除

    Args:
        client: APIクライアント
        project_uuid: プロジェクトのUUID
        measurement_uuid: 計測UUID
    """
    api = measurement_service_measurement_base_times_api.MeasurementServiceMeasurementBaseTimesApi(
        client
    )

    current_basetimes = api.list_project_measurement_base_times(
        project_uuid=project_uuid,
        measurement_uuid=measurement_uuid,
    )
    for bt_current in iter_api_items(current_basetimes):
        api.delete_project_measurement_base_time_by_id(
            project_uuid=project_uuid,
            measurement_uuid=measurement_uuid,
            id=bt_current.id,
        )
        logging.info(f"Deleted measurement base time: {bt_current.id}")


def create_basetime(
    client: ApiClient,
    project_uuid: str,
    measurement_uuid: str,
    basetime: dict,
) -> None:
    """
    基準時刻作成

    Args:
        client: APIクライアント
        project_uuid: プロジェクトのUUID
        measurement_uuid: 計測UUID
        basetime: 基準時刻
    """
    api = measurement_service_measurement_base_times_api.MeasurementServiceMeasurementBaseTimesApi(
        client
    )
    bt_copy = basetime.copy()
    bt_copy["priority"] = MeasBaseTimePriority(basetime["priority"])
    bt_copy["name"] = MeasBaseTimeName(basetime["name"])
    bt_create = CreateMeasBaseTime(**bt_copy)
    base_time = api.create_project_measurement_base_time(
        project_uuid=project_uuid,
        measurement_uuid=measurement_uuid,
        create_meas_base_time=to_api_body(bt_create),
    )
    logging.info(f"Created measurement basetime: {base_time.id}")


def create_markers(
    client: ApiClient,
    project_uuid: str,
    measurement_uuid: str,
    markers_src: list,
) -> None:
    """
    マーカー作成

    type：point/rangeで分岐してコピー
    - point: occurred_elapsed_time
    - range: start_elapsed_time, end_elapsed_time

    Args:
        client: APIクライアント
        project_uuid: プロジェクトUUID
        measurement_uuid: 計測UUID
        markers_src: マーカーリスト
    """
    api = measurement_service_measurement_markers_api.MeasurementServiceMeasurementMarkersApi(
        client
    )

    for mk_src in markers_src:
        mk_copy = mk_src.copy()
        if mk_copy["type"] == "point":
            mk_copy["detail"] = MeasurementMarkerDetailPoint(
                occurred_elapsed_time=mk_copy["detail"]["occurred_elapsed_time"],
            )
        else:
            mk_copy["detail"] = MeasurementMarkerDetailRange(
                start_elapsed_time=mk_copy["detail"]["start_elapsed_time"],
                end_elapsed_time=mk_copy["detail"]["end_elapsed_time"],
            )

        mk_create = MeasurementMarkerPostRequest(**mk_copy)
        marker = api.create_project_measurement_marker(
            project_uuid=project_uuid,
            measurement_uuid=measurement_uuid,
            measurement_marker_post_request=to_api_body(mk_create),
        )
        logging.info(f"Created measurement marker: {marker.uuid}")


def replace_measurement_sequence(
    client: ApiClient,
    project_uuid: str,
    measurement_uuid: str,
    sequence_uuid: Optional[str],
    expected_data_points: int,
    final_sequence_number: int,
) -> MeasurementSequenceGroup:
    """
    シーケンス作成・置き換え

    Args:
        client: APIクライアント
        project_uuid: プロジェクトのUUID
        measurement_uuid: 計測UUID
        sequence_uuid: シーケンスUUID
        expected_data_points: データポイント総数
        final_sequence_number: 最終シーケンス番号

    Returns:
        MeasurementSequenceGroup: 作成または更新された計測シーケンス
    """
    sequence_group = MeasurementSequenceGroupReplace(
        expected_data_points=expected_data_points,
        final_sequence_number=final_sequence_number,
    )

    api = measurement_service_measurement_sequences_api.MeasurementServiceMeasurementSequencesApi(
        client
    )
    sequence = api.replace_project_measurement_sequence(
        project_uuid=project_uuid,
        measurement_uuid=measurement_uuid,
        sequences_uuid=sequence_uuid if sequence_uuid else str(uuid.uuid4()),
        measurement_sequence_group_replace=to_api_body(sequence_group),
    )
    logging.info(f"Replaced measurement sequence: {sequence.uuid}")
    return sequence


def build_store_data_chunk(
    measurement_uuid: str,
    sequence_uuid: str,
    basetime_ns: int,
    datapoints: list,
    sequence_number: int,
) -> StoreDataChunks:
    """
    StoreDataChunks作成

    1つのStoreDataChunkに複数のデータポイントを格納する。
    データIDごとにStoreDataPointGroupを分け、各グループのdata_pointsに
    複数点を追加する。

    Args:
        measurement_uuid: 計測UUID
        sequence_uuid: シーケンスUUID
        basetime_ns: 基準時刻のUnix epochナノ秒
        datapoints: データポイントのリスト
        sequence_number: シーケンス番号

    Returns:
        StoreDataChunks: protobuf送信用のチャンク
    """
    groups: dict[tuple[int, str], list[StoreDataPoint]] = {}
    for dp in datapoints:
        elapsed_time = dp["time"] - basetime_ns
        payload = base64.b64decode(dp["data"]["d"])
        key = (dp["data_type"], dp["data_name"])
        groups.setdefault(key, []).append(
            StoreDataPoint(elapsed_time=elapsed_time, payload=payload)
        )

    data_point_groups = [
        StoreDataPointGroup(
            data_id=StoreDataID(type=data_type, name=data_name),
            data_points=points,
        )
        for (data_type, data_name), points in groups.items()
    ]
    return StoreDataChunks(
        meas_uuid=measurement_uuid,
        sequence_uuid=sequence_uuid,
        chunks=[
            StoreDataChunk(
                sequence_number=sequence_number,
                data_point_groups=data_point_groups,
            )
        ],
    )


def serialized_chunk_size(
    measurement_uuid: str,
    sequence_uuid: str,
    basetime_ns: int,
    datapoints: list,
    sequence_number: int,
) -> int:
    """
    StoreDataChunksのprotobufサイズを取得

    --max_request_bytes 指定時の分割判定に使用する。

    Args:
        measurement_uuid: 計測UUID
        sequence_uuid: シーケンスUUID
        basetime_ns: 基準時刻のUnix epochナノ秒
        datapoints: データポイントのリスト
        sequence_number: シーケンス番号

    Returns:
        int: protobufシリアライズ後のバイト数
    """
    return len(
        build_store_data_chunk(
            measurement_uuid,
            sequence_uuid,
            basetime_ns,
            datapoints,
            sequence_number,
        ).SerializeToString()
    )


def split_batches(
    buffer: list,
    next_datapoint: dict,
    measurement_uuid: str,
    sequence_uuid: str,
    basetime_ns: int,
    sequence_number: int,
    max_points_per_request: int,
    max_request_bytes: int,
) -> tuple[list, Optional[list]]:
    """
    次のデータポイントを追加した場合に送信単位を分割するか判定する。

    Args:
        buffer: 送信前のデータポイントバッファ
        next_datapoint: 追加するデータポイント
        measurement_uuid: 計測UUID
        sequence_uuid: シーケンスUUID
        basetime_ns: 基準時刻のUnix epochナノ秒
        sequence_number: シーケンス番号
        max_points_per_request: 1リクエストあたりの最大データポイント数
        max_request_bytes: 1リクエストあたりのprotobuf bodyサイズ上限。0の場合はサイズ上限で分割しない

    Returns:
        tuple[list, Optional[list]]:
          - 更新後のバッファ
          - 送信すべきバッチ。まだ送信しない場合はNone。
    """
    if len(buffer) >= max_points_per_request:
        return [next_datapoint], buffer

    if max_request_bytes <= 0:
        buffer.append(next_datapoint)
        return buffer, None

    candidate = [*buffer, next_datapoint]
    if len(candidate) == 1:
        return candidate, None

    size = serialized_chunk_size(
        measurement_uuid,
        sequence_uuid,
        basetime_ns,
        candidate,
        sequence_number,
    )
    if size > max_request_bytes:
        return [next_datapoint], buffer

    return candidate, None


def inspect_source(
    src_file: str,
    max_points_per_request: int,
    max_request_bytes: int,
) -> tuple[dict, int, int]:
    """
    入力JSON Linesを事前走査し、計測情報・データポイント数・シーケンス数を取得する。

    シーケンスの expected_data_points / final_sequence_number を正しく作成するため、
    データ投入前に総データポイント数とStoreDataChunk数を確定する。

    Args:
        src_file: 計測JSON Linesファイルパス
        max_points_per_request: 1リクエストあたりの最大データポイント数
        max_request_bytes: 1リクエストあたりのprotobuf bodyサイズ上限。0の場合はサイズ上限で分割しない

    Returns:
        tuple[dict, int, int]: 計測情報、データポイント総数、最終シーケンス番号
    """
    measurement_src: dict = {}
    data_point_count = 0
    final_sequence_number = 0

    dummy_meas_uuid = str(uuid.uuid4())
    dummy_seq_uuid = str(uuid.uuid4())
    basetime_ns: Optional[int] = None
    buffer: list = []

    for entry in load(src_file):
        if "measurement" in entry:
            measurement_src = entry["measurement"]
            basetime_ns = parse_basetime_ns(measurement_src["basetime"])
        elif "datapoint" in entry:
            if basetime_ns is None:
                raise ValueError("Measurement must be defined before datapoints")
            data_point_count += 1
            buffer, batch = split_batches(
                buffer,
                entry["datapoint"],
                dummy_meas_uuid,
                dummy_seq_uuid,
                basetime_ns,
                final_sequence_number + 1,
                max_points_per_request,
                max_request_bytes,
            )
            if batch:
                final_sequence_number += 1

    if buffer:
        final_sequence_number += 1

    if not measurement_src:
        raise ValueError("Measurement is not found in source file")

    return measurement_src, data_point_count, final_sequence_number


def create_sequence_chunks(
    api: measurement_service_measurement_sequences_api.MeasurementServiceMeasurementSequencesApi,
    project_uuid: str,
    payload: bytes,
) -> Any:
    """
    シーケンスチャンク送信

    intdash API Clientのバージョン差分を吸収するため、まずbytesをBodyに指定し、
    型検証エラーの場合のみfile-like objectで再実行する。

    Args:
        api: Measurement ServiceのシーケンスAPI
        project_uuid: プロジェクトUUID
        payload: protobufシリアライズ済みバイト列

    Returns:
        Any: チャンク送信APIのレスポンス
    """
    try:
        return api.create_project_measurement_sequence_chunks(
            project_uuid=project_uuid,
            body=payload,
            _content_type="application/vnd.iscp.v2.protobuf",
        )
    except (TypeError, ValueError):
        return api.create_project_measurement_sequence_chunks(
            project_uuid=project_uuid,
            body=io.BytesIO(payload),
            _content_type="application/vnd.iscp.v2.protobuf",
        )


def send_chunks(
    client: ApiClient,
    project_uuid: str,
    measurement_uuid: str,
    basetime_ns: int,
    sequence_uuid: str,
    datapoints: list,
    sequence_number: int,
) -> int:
    """
    データポイントをチャンクで分割送信
    - StoreDataPoint, StoreDataPointGroup, StoreDataChunk を生成
    - 1つのStoreDataChunkに複数のデータポイントを格納
    - Protobuf形式で送信

    Args:
        client (ApiClient): APIクライアント
        project_uuid (str): プロジェクトのUUID
        measurement_uuid (str): 計測UUID
        basetime_ns (int): 基準時刻のUnix epochナノ秒
        sequence_uuid (str): シーケンスのUUID
        datapoints (list): データポイントのリスト
        sequence_number (int): シーケンス番号

    Returns:
        int: 次回のシーケンス番号
    """
    api = measurement_service_measurement_sequences_api.MeasurementServiceMeasurementSequencesApi(
        client
    )

    chunk = build_store_data_chunk(
        measurement_uuid,
        sequence_uuid,
        basetime_ns,
        datapoints,
        sequence_number,
    )
    if not chunk.chunks:
        logging.info("No chunks available to send.")
        return sequence_number

    results = create_sequence_chunks(api, project_uuid, chunk.SerializeToString())
    for result in iter_api_items(results):
        logging.info(
            f"Sent sequence chunk: sequence number {result.sequence_number}, result: {result.result}"
        )

    return sequence_number + 1


def complete_measurement(
    client: ApiClient, project_uuid: str, measurement_uuid: str
) -> None:
    """
    計測完了

    Args:
        client: APIクライアント
        project_uuid: プロジェクトのUUID
        measurement_uuid: 計測UUID
    """
    api = measurement_service_measurements_api.MeasurementServiceMeasurementsApi(client)
    api.complete_project_measurement(
        project_uuid=project_uuid,
        measurement_uuid=measurement_uuid,
    )


def main(
    api_url: str,
    api_token: str,
    project_uuid: str,
    edge_uuid: str,
    src_file: str,
    max_points_per_request: int,
    max_request_bytes: int,
) -> None:
    """
    メイン（随時み出し版）
    - 計測ファイル読込
    - 計測データ作成
      - APIクライアント作成
      - 計測作成
      - 基準時刻作成
      - マーカー作成
      - シーケンス作成
      - チャンク送信
      - 計測完了

    Args:
        api_url: intdash APIのURL
        api_token: 認証用のAPIトークン
        project_uuid: プロジェクトUUID
        edge_uuid: エッジUUID
        src_file: 計測ファイルパス
    """
    logging.info(
        f"Processing project_uuid: {project_uuid}, edge_uuid: {edge_uuid}, src_file: {src_file}"
    )

    try:
        if max_points_per_request <= 0:
            raise ValueError("--max_points_per_request must be greater than 0")
        if max_request_bytes < 0:
            raise ValueError("--max_request_bytes must be greater than or equal to 0")

        measurement_src, data_point_count, final_sequence_number = inspect_source(
            src_file,
            max_points_per_request,
            max_request_bytes,
        )
        logging.info(
            "Source inspected: data_points=%s, final_sequence_number=%s",
            data_point_count,
            final_sequence_number,
        )

        # APIクライアント生成
        client = get_client(api_url, api_token)

        buffer = []

        sequence_uuid = str(uuid.uuid4())
        sequence_number = 1
        measurement: Optional[Measurement] = None
        basetime_ns = parse_basetime_ns(measurement_src["basetime"])

        for entry in load(src_file):
            if "measurement" in entry:
                markers = measurement_src.get("markers", [])
                measurement = create_measurement(
                    client, project_uuid, edge_uuid, measurement_src
                )
                create_markers(client, project_uuid, measurement.uuid, markers)
                replace_measurement_sequence(
                    client,
                    project_uuid,
                    measurement.uuid,
                    sequence_uuid,
                    data_point_count,
                    final_sequence_number,
                )
                clear_basetimes(client, project_uuid, measurement.uuid)
            elif "basetime" in entry:
                if measurement is None:
                    raise ValueError("Measurement must be defined before basetimes")
                create_basetime(
                    client, project_uuid, measurement.uuid, entry["basetime"]
                )
            elif "datapoint" in entry:
                if measurement is None:
                    raise ValueError("Measurement must be defined before datapoints")
                buffer, batch = split_batches(
                    buffer,
                    entry["datapoint"],
                    measurement.uuid,
                    sequence_uuid,
                    basetime_ns,
                    sequence_number,
                    max_points_per_request,
                    max_request_bytes,
                )
                if batch:
                    sequence_number = send_chunks(
                        client,
                        project_uuid,
                        measurement.uuid,
                        basetime_ns,
                        sequence_uuid,
                        batch,
                        sequence_number,
                    )
                    log_memory_usage()

        if buffer:
            send_chunks(
                client,
                project_uuid,
                measurement.uuid,
                basetime_ns,
                sequence_uuid,
                buffer,
                sequence_number,
            )

        # 計測完了
        if measurement is None:
            raise ValueError("Measurement is not created")
        complete_measurement(client, project_uuid, measurement.uuid)
        logging.info(f"Created measurement: {measurement.uuid}")

    except Exception as e:
        logging.error(f"Error: {str(e)}")
        logging.error(traceback.format_exc())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Input from JSON Lines and create new measurement."
    )
    parser.add_argument("--api_url", required=True, help="URL of the intdash API")
    parser.add_argument("--api_token", required=True, help="API Token")
    parser.add_argument(
        "--project_uuid",
        default="00000000-0000-0000-0000-000000000000",
        help="Project UUID (default: 00000000-0000-0000-0000-000000000000)",
    )
    parser.add_argument("--edge_uuid", required=True, help="Edge UUID")
    parser.add_argument(
        "--src_file", required=True, help="Path to the Measurement JSON Lines file"
    )
    parser.add_argument(
        "--max_points_per_request",
        type=int,
        default=DEFAULT_MAX_POINTS_PER_REQUEST,
        help=(
            "Maximum number of data points per StoreDataChunk request "
            f"(default: {DEFAULT_MAX_POINTS_PER_REQUEST})"
        ),
    )
    parser.add_argument(
        "--max_request_bytes",
        type=int,
        default=DEFAULT_MAX_REQUEST_BYTES,
        help=(
            "Maximum protobuf request body size in bytes. "
            "0 disables byte-size based splitting."
        ),
    )

    args = parser.parse_args()
    main(
        args.api_url,
        args.api_token,
        args.project_uuid,
        args.edge_uuid,
        args.src_file,
        args.max_points_per_request,
        args.max_request_bytes,
    )
