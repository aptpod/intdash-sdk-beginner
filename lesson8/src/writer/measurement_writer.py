import io
import logging
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

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

NAL_START_CODES = [b"\x00\x00\x00\x01", b"\x00\x00\x01"]


class MeasurementWriter:
    """
    計測作成

    Attributes:
        client (ApiClient): APIクライアント
        project_uuid (str): プロジェクトのUUID
        edge_uuid (str): エッジUUID
        measurement (Measurement): 新規計測
        sequence_number (int): シーケンス番号
    """

    @staticmethod
    def skip_aud(nal_bytes: bytes) -> bytes:
        """
        AUDスキップ

        AnnexB ストリームから AUD (nal_type=9) を除去

        Args:
            nal_bytes (bytes): AnnexB ストリーム

        Returns:
            bytes: AnnexB ストリーム
        """
        out = bytearray()
        i = 0
        while i < len(nal_bytes):
            starts = [(nal_bytes.find(sc, i), len(sc)) for sc in NAL_START_CODES]
            starts = [(pos, sc_len) for pos, sc_len in starts if pos != -1]

            if not starts:
                break

            # 最も手前のスタートコードを採用
            start, sc_len = min(starts, key=lambda x: x[0])

            # 次のスタートコード位置を探す
            next_positions = []
            for sc in NAL_START_CODES:
                pos = nal_bytes.find(sc, start + sc_len)
                if pos != -1:
                    next_positions.append(pos)

            end = min(next_positions, default=len(nal_bytes))
            nalu = nal_bytes[start:end]

            # NAL ヘッダ 1 バイトから nal_type を抽出
            nal_type = nalu[sc_len] & 0x1F
            if nal_type != 9:
                out.extend(nalu)

            i = end

        return bytes(out) if out else nal_bytes

    @staticmethod
    def is_idr_frame(encoded_data: bytes) -> bool:
        """
        IDRフレーム判別

        H.264データからNALUタイプを読み取り、IDRフレームかを判別する。
        - 開始コードの次のコードがNAL Unit
            - 開始コードリスト分探す
                - 開始コードが見つからない場合、IDRフレームではない
            - NALUタイプを取得
        - IDRフレーム判定
            - IDRフレーム: SPS(nal_type:7) PPS(nal_type:8) IDR(nal_type:5)が順序通りに存在

        Args:
        Return:
            bool:
                True: IDRフレーム
                False: Non-IDRフレーム、またはSPS/PPS/IDRの順序が満たされない
        """
        current_idx = 0
        sps_found = False
        pps_found = False

        while current_idx < len(encoded_data):
            # 開始コードを探す
            start_idx = -1
            start_code_length = 0

            for start_code in NAL_START_CODES:
                start_idx = encoded_data.find(start_code, current_idx)
                if start_idx != -1:
                    start_code_length = len(start_code)
                    break

            # 開始コードが見つからなかった場合は終了
            if start_idx == -1:
                break

            # NAL Unitのヘッダ位置
            nalu_header_idx = start_idx + start_code_length
            if nalu_header_idx >= len(encoded_data):
                break

            # NAL Unitタイプを取得
            nalu_header = encoded_data[nalu_header_idx]
            nalu_type = nalu_header & 0x1F

            # IDRフレームの順序判定
            if nalu_type == 7:
                sps_found = True
            elif nalu_type == 8 and sps_found:
                pps_found = True
            elif nalu_type == 5 and sps_found and pps_found:
                return True

            # 次のNAL Unitを探索するためにインデックスを更新
            current_idx = nalu_header_idx + 1

        # 全ての必要なNAL Unitが見つからなかった場合
        return False

    def __init__(self, client: ApiClient, project_uuid: str, edge_uuid: str) -> None:
        self.client = client
        self.project_uuid = project_uuid
        self.edge_uuid = edge_uuid
        self.measurement = None
        self.sequence_number = 1

    def create_measurement(self, name: str, basetime: datetime) -> Measurement:
        """
        計測作成

        Args:
            name (str): 名前
            basetime (datetime): 基準時刻

        Returns:
            Measurement: 作成された計測オブジェクト
        """
        meas_dict: Dict[str, object] = {}
        meas_dict["edge_uuid"] = self.edge_uuid
        meas_dict["name"] = name
        meas_dict["basetime"] = basetime
        meas_dict["basetime_type"] = MeasurementBaseTimeType("manual")
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
            sequence_uuid: シーケンスUUID
            count: データポイント数

        Returns:
            MeasurementSequenceGroup: 作成または更新された計測シーケンス


        Raises:
            RuntimeError: create_measurement() が呼ばれていない場合
        """
        if not self.measurement:
            raise RuntimeError("Measurement is None")

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
        data_name: str,
        frames: list[Tuple[int, bytes]],
    ) -> Tuple[CreateMeasurementChunksResult, List[bool]]:
        """
        チャンク送信

        NAL Unit Type: AUD(9)をスキップする。Data Visualizerでのデコードのため。
        フレームのIDR/Non-IDR判定してデータ型名を決定する。

        Args:
            sequence_uuid (str): シーケンスのUUID
            dana_name (str): データ名
            frames (list): フレームリスト [(pts_ns, payload), ...]

        Returns:
            CreateMeasurementChunksResult: チャンク送信結果
            list[bool]: 各フレームの IDR 判定結果（True=IDR, False=Non-IDR）
        """
        if not self.measurement:
            raise RuntimeError("Measurement is None")

        chunks = []
        idr_flags: List[bool] = []

        for point_time, frame in frames:
            elapsed_time = point_time
            payload = MeasurementWriter.skip_aud(frame)

            store_data_point = StoreDataPoint(
                elapsed_time=elapsed_time,
                payload=payload,
            )

            is_idr = self.is_idr_frame(payload)
            idr_flags.append(is_idr)

            type_name = "h264_frame/idr_frame" if is_idr else "h264_frame/non_idr_frame"
            store_data_point_group = StoreDataPointGroup(
                data_id=StoreDataID(type=type_name, name=data_name),
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
            return CreateMeasurementChunksResult(), idr_flags

        api = measurement_service_measurement_sequences_api.MeasurementServiceMeasurementSequencesApi(
            self.client
        )
        results = api.create_project_measurement_sequence_chunks(
            project_uuid=self.project_uuid,
            body=io.BytesIO(chunk.SerializeToString()),
            _content_type="application/vnd.iscp.v2.protobuf",
        )
        return results, idr_flags

    def complete_measurement(self) -> None:
        """
        計測完了
        """
        if not self.measurement:
            raise RuntimeError("Measurement is None")

        api = measurement_service_measurements_api.MeasurementServiceMeasurementsApi(
            self.client
        )
        api.complete_project_measurement(
            project_uuid=self.project_uuid, measurement_uuid=self.measurement.uuid
        )
