import asyncio
import logging
from datetime import datetime
from pathlib import Path

from convertor.convertor import Convertor
from writer.measurement_writer import MeasurementWriter


class UploadService:
    """
    動画アップロードサービス

    MP4ファイル変換Gstreamerパイプライン、計測作成、フレーム送信を管理する

    Attributes:
        converter (Convertor): AVCC→AnnexBコンバーター
        writer (MeasurementWriter): 計測作成
    """

    def __init__(
        self,
        convertor: Convertor,
        writer: MeasurementWriter,
        fetch_size: int = 100,
    ) -> None:
        self.convertor = convertor
        self.writer = writer
        self.fetch_size = fetch_size

    async def start(self, filepath: Path, data_name: str, basetime: datetime) -> None:
        """
        開始

        Args:
            filepath (Path): MP4ファイルパス
            data_name (str): データ名
            basetime (datetime): 基準時刻

        計測作成
        Gstreamerパイプライン開始
        以下を実行
        - フレーム送信
            - AVCCからAnnexBに変換されたH.264データを取得
            - チャンク送信
        計測完了
        """
        try:
            measurement = self.writer.create_measurement(
                f"Created from {filepath.name}",
                basetime,
            )
            logging.info(f"Created measurement: {measurement.uuid}")

            self.convertor.start()

            fetch_task = asyncio.create_task(self.fetch(data_name))  # H.264フレーム取得

            await asyncio.gather(fetch_task)

        except asyncio.CancelledError:
            pass
        finally:
            self.writer.complete_measurement()
            logging.info(f"Completed measurement: {measurement.uuid}")

    async def fetch(self, data_name: str) -> None:
        """
        H.264フレーム取得

        Annex B変換されたH.264フレームを取得する。

        Args:
            data_name (str): データ名

        - フレームリスト取得
        - チャンク送信
        """
        sequence_uuid = None
        count = 0
        idr_count = 0
        while True:
            frames = await self.convertor.fetch(self.fetch_size)
            if not frames:
                break

            # シーケンス作成・更新
            count = count + len(frames)
            sequence = self.writer.replace_measurement_sequence(
                sequence_uuid if sequence_uuid else None,
                count,
            )

            # チャンク送信
            sequence_uuid = sequence.uuid
            results = self.writer.send_chunks(sequence.uuid, data_name, frames)
            for result in results[0].items:
                logging.info(
                    f"Sent sequence chunk: sequence number {result.sequence_number}, result: {result.result}"
                )
            idr_count = idr_count + sum(results[1])

        non_idr_count = count - idr_count
        ratio = (idr_count / count * 100.0) if count > 0 else 0.0
        logging.info(
            f"Total frames: {count:,} IDR: {idr_count:,} Non-IDR: {non_idr_count:,} IDR ratio: {ratio:.2f}%"
        )

    async def close(self) -> None:
        """
        終了
        """
        self.convertor.stop()
        pass
