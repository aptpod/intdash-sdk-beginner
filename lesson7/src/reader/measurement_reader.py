import base64
import json
from datetime import datetime
from typing import Generator, Optional, Tuple

from intdash import ApiClient
from intdash.api import (
    measurement_service_data_points_api,
    measurement_service_measurements_api,
)


class MeasurementReader:
    """
    計測取得

    Attributes:
        client (ApiClient): APIクライアント
        project_uuid (str): プロジェクトUUID
        edge_uuid (str): エッジUUID
        meas_uuid (str): 計測UUID
        start (str): 開始時刻（RFC3339形式）
        end (str): 終了時刻（RFC3339形式）
        data_id_filter (list): データ型名:データ名
    """

    def __init__(
        self,
        client: ApiClient,
        project_uuid: str,
        edge_uuid: Optional[str] = None,
        meas_uuid: Optional[str] = None,
        start: Optional[str] = None,
        end: Optional[str] = None,
        data_id_filter: Optional[list] = None,
    ) -> None:
        self.client = client
        self.project_uuid = project_uuid
        self.edge_uuid = edge_uuid
        self.meas_uuid = meas_uuid
        self.start = start
        self.end = end
        self.data_id_filter = data_id_filter

    def get_basetime(self) -> datetime:
        """
        基準時刻取得

        - 開始時刻指定時：開始時刻
        - 開始時刻未指定時：計測の開始時刻

        Returns:
            basetime: 基準時刻
        """
        if self.start:
            return datetime.fromisoformat(self.start)

        api = measurement_service_measurements_api.MeasurementServiceMeasurementsApi(
            self.client
        )
        measurement = api.get_project_measurement(
            project_uuid=self.project_uuid, measurement_uuid=self.meas_uuid
        )
        return measurement.basetime

    def get_datapoints(
        self,
        chunk_size: int = 262144,  # 256KB
    ) -> Generator[Tuple[int, str, str, bytes], None, None]:
        """
        データポイント取得

        チャンク転送エンコーディング（Transfer-Encoding: chunked）のエンドポイントで逐次的にデータを取得する
        データチャンクサイズごとに取得してバッファに溜め込み、
        JSON Line形式1行（改行コード）ごとにパースして返却

        Args:
            chunk_size (int): データチャンクサイズ

        Yields:
            tuple: データポイント
                絶対時刻（ナノ秒精度POSIX）
                データ型名
                データ名
                データ（bytes）
        """

        api = measurement_service_data_points_api.MeasurementServiceDataPointsApi(
            self.client
        )
        params: dict[str, object] = {
            "project_uuid": self.project_uuid,
            "name": self.meas_uuid if self.meas_uuid else self.edge_uuid,
            "time_format": "ns",
            "_preload_content": False,  # 全データロードの抑止
        }
        if self.start:
            params["start"] = self.start
        if self.end:
            params["end"] = self.end
        if self.data_id_filter:
            params["data_id_filter"] = self.data_id_filter
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

                yield (
                    line_json["time"],
                    line_json["data_type"],
                    line_json["data_name"],
                    base64.b64decode(line_json["data"]["d"]),
                )
