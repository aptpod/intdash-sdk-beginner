import base64
import json
import struct
from datetime import datetime, timezone

from intdash import ApiClient
from intdash.api import (
    measurement_service_data_points_api,
    measurement_service_measurements_api,
)
from intdash.model.measurement import Measurement


class MeasurementReader:
    """
    計測取得

    Attributes:
        client (ApiClient): APIクライアント
        project_uuid (str): プロジェクトUUID
        meas_uuid (str): 計測UUID
        start (str): 日付時刻文字列
    """

    def __init__(self, client: ApiClient, project_uuid: str, meas_uuid: str) -> None:
        self.client = client
        self.project_uuid = project_uuid
        self.meas_uuid = meas_uuid
        self.start = datetime.fromtimestamp(0, tz=timezone.utc).isoformat()

    def get_measurement(self) -> Measurement:
        """
        計測取得

        Returns:
            Measurement: 計測オブジェクト
        """
        api = measurement_service_measurements_api.MeasurementServiceMeasurementsApi(
            self.client
        )
        measurement = api.get_project_measurement(
            project_uuid=self.project_uuid, measurement_uuid=self.meas_uuid
        )
        return measurement

    def get_coordinates(self, fetch_size: int = 100) -> list:
        """
        位置情報取得

        計測のGNSSデータのうち、"#:1/gnss_coordinates"のみ取得
        データポイント（JSONLines形式）ごとの["data"]["d"]（2D Vector形式）をパースして位置情報に変換
        前回データポイントの時刻+1からフェッチ開始

        Args:
            fetch_size (int): フェッチ件数

        Returns:
            list: 位置情報(time, lat, lon)のリスト
        """
        api = measurement_service_data_points_api.MeasurementServiceDataPointsApi(
            self.client
        )
        stream = api.list_project_data_points(
            project_uuid=self.project_uuid,
            name=self.meas_uuid,
            data_id_filter=["#:1/gnss_coordinates"],
            start=self.start,
            limit=fetch_size,
            time_format="ns",
        )

        coordinates = []
        last_time = None
        while True:
            line = stream.readline()
            if not line:
                break

            line_json = json.loads(line.decode())
            if "data" in line_json and "d" in line_json["data"]:
                base64_encoded = line_json["data"]["d"]
                bin_data = base64.b64decode(base64_encoded)
                x, y = struct.unpack(">dd", bin_data)
                coordinates.append((line_json["time"], (x, y)))
                last_time = line_json["time"]

        if not last_time:
            return []

        self.start = datetime.fromtimestamp(
            (last_time // 1_000 + 1) / 1_000_000, tz=timezone.utc
        ).isoformat()

        return coordinates
