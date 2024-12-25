import asyncio
import logging
import time

import iscp
from convertor.convertor import Convertor
from snapper.snapper import Snapper
from upstreamer.upstreamer import Upstreamer
from writer.measurement_writer import MeasurementWriter


class CaptureService:
    """
    画面キャプチャサービス

    画面キャプチャ、アップストリームを管理する

    Attributes:
        snapper (Snapper): 画面キャプチャ
        encoder (Convertor): エンコーダー
        writer (MeasurementWriter): 計測作成
        upstreamer (Upstreamer): アップストリーマー
        fps (int): FPS
    """

    def __init__(
        self,
        snapper: Snapper,
        encoder: Convertor,
        writer: MeasurementWriter,
        upstreamer: Upstreamer,
        fps: int,
    ) -> None:
        self.snapper = snapper
        self.encoder = encoder
        self.writer = writer
        self.upstreamer = upstreamer
        self.fps = fps

    async def start(self) -> None:
        """
        開始

        計測作成
        アップストリーム開始
        エンコーダーGstreamerパイプライン開始
        以下を並列実行
        - 画面キャプチャ
            - RAWフレームをGStreamerエンコードパイプラインに渡す
        - H.264データ取得
            - エンコードされたH.264データをアップストリーム
        Ctrl+Cで終了時に計測完了
        """
        try:
            measurement = self.writer.create_measurement("Created by CaptureService")
            logging.info(f"Created measurement: {measurement.uuid}")

            await self.upstreamer.open(measurement.uuid)

            self.encoder.start()

            capture_task = asyncio.create_task(self.capture())  # 画面キャプチャ
            fetch_task = asyncio.create_task(self.fetch())  # H.264データ取得

            await asyncio.gather(capture_task, fetch_task)

        except asyncio.CancelledError:
            self.writer.complete_measurement(measurement.uuid)
            logging.info(f"Completed measurement: {measurement.uuid}")

    async def capture(self) -> None:
        """
        画面キャプチャ

        - スクリーン全体キャプチャ
        - エンコーダ入力
        """
        frame_interval = 1.0 / self.fps
        next_frame_time = time.monotonic()  # 次のフレームの基準時間

        while True:
            frame = self.snapper.get()
            await self.encoder.push(frame)

            next_frame_time += frame_interval
            sleep_time = max(next_frame_time - time.monotonic(), 0)
            await asyncio.sleep(sleep_time)

    async def fetch(self) -> None:
        """
        H.264データ取得

        - エンコードデータ取得
        - H.264データアップストリーム
        """

        start = iscp.DateTime.utcnow()
        while True:
            frame = await self.encoder.get()

            elapsed_time = iscp.DateTime.utcnow().unix_nano() - start.unix_nano()
            await self.upstreamer.send(elapsed_time, frame)
            logging.info(f"Sent elapsed_time {elapsed_time} {len(frame)} bytes")

    async def close(self) -> None:
        """
        終了
        """
        self.encoder.stop()
        await self.upstreamer.close()
