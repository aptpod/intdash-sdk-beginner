from datetime import datetime, timezone

from intdash import ApiClient
from intdash.api import (
    measurement_service_measurements_api,
)
from intdash.model.meas_base_time_name import MeasBaseTimeName
from intdash.model.meas_base_time_priority import MeasBaseTimePriority
from intdash.model.meas_create import MeasCreate
from intdash.model.measurement import Measurement
from intdash.model.measurement_base_time_type import MeasurementBaseTimeType


class MeasurementWriter:
    """
    計測作成

    Attributes:
        client (ApiClient): APIクライアント
        project_uuid (str): プロジェクトのUUID
        edge_uuid （str): エッジUUID
    """

    def __init__(self, client: ApiClient, project_uuid: str, edge_uuid: str) -> None:
        self.client = client
        self.project_uuid = project_uuid
        self.edge_uuid = edge_uuid

    def create_measurement(self, name: str) -> Measurement:
        """
        計測作成

        Args:
            name (str): 計測名

        Returns:
            Measurement: 作成された計測オブジェクト
        """
        basetime = datetime.now(tz=timezone.utc)
        meas_create = MeasCreate(
            name=name,
            basetime=basetime,
            basetime_type=MeasurementBaseTimeType("manual"),
            basetime_priority=MeasBaseTimePriority(0),
            basetime_name=MeasBaseTimeName("Temporary"),
            edge_uuid=self.edge_uuid,
            protected=False,
        )

        api = measurement_service_measurements_api.MeasurementServiceMeasurementsApi(
            self.client
        )
        measurement = api.create_project_measurement(
            self.project_uuid, meas_create=meas_create
        )
        return measurement

    def complete_measurement(self, measurement_uuid: str) -> None:
        """
        計測完了

        Args:
            measurement_uuid: 計測UUID
        """
        api = measurement_service_measurements_api.MeasurementServiceMeasurementsApi(
            self.client
        )
        api.complete_project_measurement(
            measurement_uuid=measurement_uuid, project_uuid=self.project_uuid
        )
