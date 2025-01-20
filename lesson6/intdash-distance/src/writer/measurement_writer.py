import io
import logging
import struct
import uuid
from typing import Optional

from gen.intdash.v1.protocol_pb2 import (  # type: ignore
    StoreDataChunk,
    StoreDataChunks,
    StoreDataID,
    StoreDataPoint,
    StoreDataPointGroup,
)
from intdash import ApiClient
from intdash.api import (
    measurement_service_measurement_sequences_api,
    measurement_service_measurements_api,
)
from intdash.model.create_measurement_chunks_result import CreateMeasurementChunksResult
from intdash.model.meas_create import MeasCreate
from intdash.model.measurement import Measurement
from intdash.model.measurement_base_time_type import MeasurementBaseTimeType
from intdash.model.measurement_sequence_group import MeasurementSequenceGroup
from intdash.model.measurement_sequence_group_replace import (
    MeasurementSequenceGroupReplace,
)


class MeasurementWriter:
    """
    計測作成

    Attribute:
        client (ApiClient): APIクライアント
        project_uuid (str): プロジェクトのUUID
        measurement (Measurement): 新規計測
        sequence_number (int): シーケンス番号
    """

    def __init__(self, client: ApiClient, project_uuid: str) -> None:
        self.client = client
        self.project_uuid = project_uuid
        self.measurement = None
        self.sequence_number = 1

    def create_measurement(self, src: Measurement) -> Measurement:
        """
        計測作成

        Args:
            src: 元計測
        Returns:
            Measurement: 作成された計測オブジェクト
        """
        meas_dict = src.to_dict()
        meas_dict["name"] = f"Created from {src.uuid}"
        meas_dict["basetime_type"] = MeasurementBaseTimeType(meas_dict["basetime_type"])
        meas_dict["protected"] = False
        meas_create = MeasCreate(**meas_dict)

        api = measurement_service_measurements_api.MeasurementServiceMeasurementsApi(
            self.client
        )
        measurement = api.create_project_measurement(
            self.project_uuid, meas_create=meas_create
        )
        self.measurement = measurement
        return measurement

    def replace_measurement_sequence(
        self,
        sequence_uuid: Optional[str],
        count: int,
    ) -> MeasurementSequenceGroup:
        """
        シーケンス作成・置き換え

        Args:
            project_uuid: プロジェクトのUUID
            measurement: 計測情報
            sequence_uuid: シーケンスUUID
            count: データポイント数

        Returns:
            MeasurementSequenceGroup: 作成または更新された計測シーケンス
        """
        if not self.measurement:
            raise

        sequence_group = MeasurementSequenceGroupReplace(
            expected_data_points=count,
            final_sequence_number=count,
        )

        api = measurement_service_measurement_sequences_api.MeasurementServiceMeasurementSequencesApi(
            self.client
        )
        sequence = api.replace_project_measurement_sequence(
            project_uuid=self.project_uuid,
            measurement_uuid=self.measurement.uuid,
            sequences_uuid=sequence_uuid if sequence_uuid else str(uuid.uuid4()),
            measurement_sequence_group_replace=sequence_group,
        )
        return sequence

    def send_chunks(
        self,
        sequence_uuid: str,
        distances: list,
    ) -> CreateMeasurementChunksResult:
        """
        チャンク送信

        Args:
            project_uuid: プロジェクトのUUID
            measurement: 計測情報
            sequence_uuid: シーケンスのUUID
            distances: 距離リスト

        Returns:
            CreateMeasurementChunksResult: チャンク送信結果
        """
        if not self.measurement:
            raise

        chunks = []
        # floatで計算すると丸めが発生するため、intにしてからさらに1000を掛ける
        basetime_ns = int(self.measurement.basetime.timestamp() * 1_000_000) * 1_000

        for point_time, distance in distances:
            elapsed_time = point_time - basetime_ns
            store_data_point = StoreDataPoint(
                elapsed_time=elapsed_time,
                payload=struct.pack(">d", distance),
            )
            store_data_point_group = StoreDataPointGroup(
                data_id=StoreDataID(type="float64", name="10/distance"),
                data_points=[store_data_point],
            )
            store_data_chunk = StoreDataChunk(
                sequence_number=self.sequence_number,
                data_point_groups=[store_data_point_group],
            )
            chunks.append(store_data_chunk)
            self.sequence_number += 1

        chunk = StoreDataChunks(
            meas_uuid=self.measurement.uuid, sequence_uuid=sequence_uuid, chunks=chunks
        )
        if not chunk.chunks:
            logging.warning("No chunks available to send.")
            return CreateMeasurementChunksResult()

        api = measurement_service_measurement_sequences_api.MeasurementServiceMeasurementSequencesApi(
            self.client
        )
        results = api.create_project_measurement_sequence_chunks(
            project_uuid=self.project_uuid,
            body=io.BytesIO(chunk.SerializeToString()),
            _content_type="application/vnd.iscp.v2.protobuf",
        )
        return results

    def complete_measurement(self) -> None:
        """
        計測完了
        """
        if not self.measurement:
            raise

        api = measurement_service_measurements_api.MeasurementServiceMeasurementsApi(
            self.client
        )
        api.complete_project_measurement(
            project_uuid=self.project_uuid, measurement_uuid=self.measurement.uuid
        )

    def delete_measurement(self) -> None:
        """
        計測削除
        """
        if not self.measurement:
            raise

        api = measurement_service_measurements_api.MeasurementServiceMeasurementsApi(
            self.client
        )
        api.delete_project_measurement(
            project_uuid=self.project_uuid, measurement_uuid=self.measurement.uuid
        )
