import argparse
import json
import logging
import sys
import traceback
from datetime import datetime
from typing import Any, Generator

import psutil

from intdash import ApiClient, Configuration
from intdash.api import (
    measurement_service_data_points_api,
    measurement_service_measurement_base_times_api,
    measurement_service_measurements_api,
)
from intdash.model.measurement import Measurement

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

DATA_PATH = "."


class MeasurementEncoder(json.JSONEncoder):
    """
    計測エンコーダー
    - datetime
      - ナノ秒対応
      - タイムゾーン考慮
    """

    def default(self, obj: Any) -> Any:
        """
        エンコード

        Args:
            obj (Any): JSON各項目

        Returns:
            Any: 変換後各項目
        """
        if isinstance(obj, datetime):
            iso_str = obj.isoformat()
            if obj.microsecond:
                nano_str = "{:09d}".format(obj.microsecond * 1000)
                iso_str = iso_str.replace(f".{obj.microsecond:06d}", f".{nano_str}")
            return iso_str

        if hasattr(obj, "to_dict"):
            return obj.to_dict()

        return super().default(obj)


def log_memory_usage() -> None:
    """
    メモリ使用量出力
    """
    process = psutil.Process()
    mem_info = process.memory_info()
    logging.info(f"Memory Usage: {mem_info.rss / 1024 / 1024:.2f} MB")


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


def get_measurement(
    client: ApiClient, project_uuid: str, meas_uuid: str
) -> Measurement:
    """
    計測取得

    Args:
        client: APIクライアント
        project_uuid: プロジェクトUUID
        meas_uuid: 計測UUID

    Returns:
        Measurement: 計測オブジェクト
    """
    api = measurement_service_measurements_api.MeasurementServiceMeasurementsApi(client)
    measurement = api.get_project_measurement(
        project_uuid=project_uuid, measurement_uuid=meas_uuid
    )
    logging.info(f"Download measurement: {measurement.uuid}")
    return measurement


def get_basetimes(client: ApiClient, project_uuid: str, meas_uuid: str) -> list:
    """
    計測基準時刻リスト取得

    Args:
        client: APIクライアント
        project_uuid: プロジェクトUUID
        meas_uuid: 計測UUID

    Returns:
        list: 計測基準時刻リスト
    """
    api = measurement_service_measurement_base_times_api.MeasurementServiceMeasurementBaseTimesApi(
        client
    )
    basetimes = api.list_project_measurement_base_times(
        project_uuid=project_uuid, measurement_uuid=meas_uuid
    )
    count = len(basetimes["items"])
    logging.info(f"Download basetimes: {count}")
    return basetimes["items"]


def get_datapoints(
    client: ApiClient,
    project_uuid: str,
    meas_uuid: str,
    chunk_size: int = 262144,  # 256KB
) -> Generator[dict, None, None]:
    """
    計測データポイント取得

    Args:
        client: APIクライアント
        project_uuid: プロジェクトUUID
        meas_uuid: 計測UUID
        chunk_size (int): データチャンクサイズ

    Yields:
        dict: データポイント
    """
    api = measurement_service_data_points_api.MeasurementServiceDataPointsApi(client)
    params = {
        "project_uuid": project_uuid,
        "name": meas_uuid,
        "time_format": "ns",
        "_preload_content": False,
    }
    stream = api.list_project_data_points(**params)
    if stream is None:
        raise Exception("Error: stream is None")

    # バッファ格納
    buffer = b""
    while True:
        chunk = stream.read(chunk_size)
        if not chunk:
            break
        buffer += chunk

        # JSON Line切り出し
        while b"\n" in buffer:
            line, buffer = buffer.split(b"\n", 1)
            line_json = json.loads(line.decode())
            if "data" not in line_json:
                continue
            if "d" not in line_json["data"]:
                continue
            yield line_json


def save(
    measurement: Measurement,
    basetimes: list,
    datapoints: Generator[dict, None, None],
    file_path: str,
) -> None:
    """
    データファイル保存

    Args:
        measurement: 計測オブジェクト
        basetimes: 計測基準時刻リスト
        datapoints: データポイント（ジェネレータ）
        file_path: ファイルパス
    """
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(
            {"measurement": measurement}, f, cls=MeasurementEncoder, ensure_ascii=False
        )
        f.write("\n")

        for bt in basetimes:
            json.dump({"basetime": bt}, f, cls=MeasurementEncoder, ensure_ascii=False)
            f.write("\n")

        for dp in datapoints:
            json.dump({"datapoint": dp}, f, cls=MeasurementEncoder, ensure_ascii=False)
            f.write("\n")
            log_memory_usage()


def main(api_url: str, api_token: str, project_uuid: str, meas_uuid: str) -> None:
    """
    メイン（随時取得版）
    - 計測データ取得
      - 計測、基準時刻、データポイントを取得
    - 計測ファイル保存
      - 以下の形式でJSON Linesファイルを保存する
        {"measurement": <計測オブジェクト>}
        {"basetime": <基準時刻>}
        {"basetime": <基準時刻>}
        ...
        {"datapoint": <データポイント>}
        {"datapoint": <データポイント>}
        ...

    Args:
        api_url: intdash APIのURL
        api_token: 認証用のAPIトークン
        project_uuid: プロジェクトUUID
        meas_uuid: 計測UUID
    """
    logging.info(f"Processing project_uuid: {project_uuid}, meas_uuid: {meas_uuid}")

    try:
        # 計測データ取得
        client = get_client(api_url, api_token)
        measurement = get_measurement(client, project_uuid, meas_uuid)
        basetimes = get_basetimes(client, project_uuid, meas_uuid)
        datapoints = get_datapoints(client, project_uuid, meas_uuid)

        # 計測ファイル保存
        dst_file = f"{DATA_PATH}/measurement_{meas_uuid}.jsonl"
        save(measurement, basetimes, datapoints, dst_file)
        logging.info(f"Saved: {dst_file}")

    except Exception as e:
        logging.error(f"Error: {str(e)}")
        logging.error(traceback.format_exc())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process measurement data and output to JSON."
    )
    parser.add_argument("--api_url", required=True, help="URL of the intdash API")
    parser.add_argument("--api_token", required=True, help="API Token")
    parser.add_argument(
        "--project_uuid",
        default="00000000-0000-0000-0000-000000000000",
        help="Project UUID (default: 00000000-0000-0000-0000-000000000000)",
    )
    parser.add_argument("--meas_uuid", required=True, help="Measurement UUID")

    args = parser.parse_args()
    main(args.api_url, args.api_token, args.project_uuid, args.meas_uuid)
