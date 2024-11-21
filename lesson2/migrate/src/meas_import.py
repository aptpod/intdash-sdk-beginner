import argparse
import base64
import io
import json
import logging
import sys
import traceback
import uuid
from datetime import datetime, timezone
from typing import Optional

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


def get_client(api_url: str, api_token: str) -> ApiClient:
    """
    APIクライアント取得

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
    measurement = api.create_project_measurement(project_uuid, meas_create=meas_create)
    logging.info(
        f"Created measurement: {measurement.uuid} edge_uuid {measurement.edge_uuid}"
    )
    return measurement


def create_basetimes(
    client: ApiClient,
    project_uuid: str,
    measurement_uuid: str,
    base_times_src: list,
) -> None:
    """
    基準時刻作成

    計測作成で作成した基準時刻を削除し、改めて基準時刻を作成

    Args:
        client: APIクライアント
        project_uuid: プロジェクトのUUID
        measurement_uuid: 計測UUID
        base_times_src: 基準時刻の詳細情報のリスト
    """
    api = measurement_service_measurement_base_times_api.MeasurementServiceMeasurementBaseTimesApi(
        client
    )

    current_basetimes = api.list_project_measurement_base_times(
        project_uuid=project_uuid,
        measurement_uuid=measurement_uuid,
    )
    for bt_current in current_basetimes["items"]:
        api.delete_project_measurement_base_time_by_id(
            project_uuid=project_uuid,
            measurement_uuid=measurement_uuid,
            id=bt_current.id,
        )
        logging.info(f"Deleted measurement base time: {bt_current.id}")

    for bt_src in base_times_src:
        bt_copy = bt_src.copy()
        bt_copy["priority"] = MeasBaseTimePriority(bt_src["priority"])
        bt_copy["name"] = MeasBaseTimeName(bt_src["name"])
        bt_create = CreateMeasBaseTime(**bt_copy)
        base_time = api.create_project_measurement_base_time(
            project_uuid=project_uuid,
            measurement_uuid=measurement_uuid,
            create_meas_base_time=bt_create,
        )
        logging.info(f"Created measurement base time: {base_time.id}")


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
            measurement_marker_post_request=mk_create,
        )
        logging.info(f"Created measurement marker: {marker.uuid}")


def replace_measurement_sequence(
    client: ApiClient,
    project_uuid: str,
    measurement_uuid: str,
    sequence_uuid: Optional[str],
    measurement_src: dict,
) -> MeasurementSequenceGroup:
    """
    シーケンス作成・置き換え

    Args:
        client: APIクライアント
        project_uuid: プロジェクトのUUID
        measurement_uuid: 計測UUID
        sequence_uuid: シーケンスUUID
        measurement_src: 計測情報

    Returns:
        MeasurementSequenceGroup: 作成または更新された計測シーケンス
    """
    sequence_group = MeasurementSequenceGroupReplace(
        expected_data_points=measurement_src["sequences"]["expected_data_points"],
        final_sequence_number=measurement_src["sequences"]["received_data_points"],
    )

    api = measurement_service_measurement_sequences_api.MeasurementServiceMeasurementSequencesApi(
        client
    )
    sequence = api.replace_project_measurement_sequence(
        project_uuid=project_uuid,
        measurement_uuid=measurement_uuid,
        sequences_uuid=sequence_uuid if sequence_uuid else str(uuid.uuid4()),
        measurement_sequence_group_replace=sequence_group,
    )
    logging.info(f"Replaced measurement sequence: {sequence.uuid}")
    return sequence


def send_chunks(
    client: ApiClient,
    project_uuid: str,
    measurement_uuid: str,
    basetime: datetime,
    sequence_uuid: str,
    data_points: list,
) -> None:
    """
    チャンク送信

    Args:
        client: APIクライアント
        project_uuid: プロジェクトのUUID
        measurement_uuid: 計測UUID
        basetime: 計測の基準時刻
        sequence_uuid: シーケンスのUUID
        data_points: データポイントのリスト
    """
    chunks = []
    sequence_number = 1
    basetime_ns = int(basetime.timestamp() * 1_000_000) * 1_000
    for i, data_point in enumerate(data_points):
        point_time = data_point["time"]
        elapsed_time = point_time - basetime_ns
        payload = base64.b64decode(data_point["data"]["d"])
        store_data_point = StoreDataPoint(elapsed_time=elapsed_time, payload=payload)

        store_data_point_group = StoreDataPointGroup(
            data_id=StoreDataID(
                type=data_point["data_type"], name=data_point["data_name"]
            ),
            data_points=[store_data_point],
        )

        store_data_chunk = StoreDataChunk(
            sequence_number=sequence_number, data_point_groups=[store_data_point_group]
        )

        chunks.append(store_data_chunk)
        sequence_number += 1

    chunk = StoreDataChunks(
        meas_uuid=measurement_uuid, sequence_uuid=sequence_uuid, chunks=chunks
    )
    if not chunk.chunks:
        logging.info("No chunks available to send.")
        return

    api = measurement_service_measurement_sequences_api.MeasurementServiceMeasurementSequencesApi(
        client
    )

    results = api.create_project_measurement_sequence_chunks(
        project_uuid=project_uuid,
        body=io.BytesIO(chunk.SerializeToString()),
        _content_type="application/vnd.iscp.v2.protobuf",
    )
    for result in results.items:
        logging.info(
            f"Sent sequence chunk: sequence number {result.sequence_number}, result: {result.result}"
        )


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
        project_uuid=project_uuid, measurement_uuid=measurement_uuid
    )


def main(
    api_url: str, api_token: str, project_uuid: str, edge_uuid: str, src_file: str
) -> None:
    """
    メイン
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
        f"Processing project_uuid: {project_uuid}, edge_uuid: {
            edge_uuid}, src_file: {src_file}"
    )

    try:
        # 計測ファイル読込
        with open(src_file, "r", encoding="utf-8") as json_file:
            data = json.load(json_file, object_hook=measurement_decoder)

        # 計測データ作成
        client = get_client(api_url, api_token)
        measurement = create_measurement(
            client, project_uuid, edge_uuid, data["measurement"]
        )
        create_basetimes(client, project_uuid, measurement.uuid, data["basetimes"])
        create_markers(
            client, project_uuid, measurement.uuid, data["measurement"]["markers"]
        )
        sequence = replace_measurement_sequence(
            client, project_uuid, measurement.uuid, None, data["measurement"]
        )
        send_chunks(
            client,
            project_uuid,
            measurement.uuid,
            data["measurement"]["basetime"],
            sequence.uuid,
            data["datapoints"],
        )
        complete_measurement(client, project_uuid, measurement.uuid)

        logging.info(f"Created measurement: {measurement.uuid}")

    except Exception as e:
        logging.error(f"Error: {str(e)}")
        logging.error(traceback.format_exc())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Input from JSON and create new measurement."
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
        "--src_file", required=True, help="Path to the Measurement JSON file"
    )

    args = parser.parse_args()
    main(
        args.api_url,
        args.api_token,
        args.project_uuid,
        args.edge_uuid,
        args.src_file,
    )
