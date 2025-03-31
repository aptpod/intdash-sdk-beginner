import asyncio
import logging

from convertor.convertor import Convertor
from detector.detector import Detector
from downstreamer.downstreamer import Downstreamer
from upstreamer.upstreamer import Upstreamer
from writer.measurement_writer import MeasurementWriter


class DetectService:
    """
    物体検出サービス

    ダウンストリーム、物体検出、アップストリームを管理する

    Attributes:
        downstreamer (Downstreamer): ダウンストリーマー
        decoder (Convertor): デコーダー
        detector (Detector): 物体検出器
        encoder (Convertor): エンコーダー
        writer (MeasurementWriter): 計測作成
        upstreamer (Upstreamer): アップストリーマー
        elapsed_time_queue (Queue): 基準時刻キュー
        count_queue (Queue): 検出数キュー
    """

    def __init__(
        self,
        downstreamer: Downstreamer,
        decoder: Convertor,
        detector: Detector,
        encoder: Convertor,
        writer: MeasurementWriter,
        upstreamer: Upstreamer,
    ) -> None:
        self.downstreamer = downstreamer
        self.decoder = decoder
        self.detector = detector
        self.encoder = encoder
        self.writer = writer
        self.upstreamer = upstreamer
        self.elapsed_time_queue: asyncio.Queue[int] = asyncio.Queue()
        self.count_queue: asyncio.Queue[int] = asyncio.Queue()

    async def start(self, read_timeout: float = 60) -> None:
        """
        開始

        Args:
            read_timeout (float): ダウンストリームタイムアウト (秒)

        検出後データ用計測作成
        ダウンストリーム開始、アップストリーム開始
        デコーダー、エンコーダーGstreamerパイプライン開始
        以下を並列実行
        - H.264データ供給
            - ダウンストリームした基準時刻をキューに追加
            - ダウンストリームしたH.264データをGStreamerデコードパイプラインに渡す
        - 物体検出
            - デコードされたRAWフレームをOpenCVで物体検出して矩形描画
            - 検出人数キューに追加
            - RAWフレームをGStreamerエンコードパイプラインに渡す
        - H.264データ取得
            - 基準時刻キューから基準時刻を取得
            - エンコードされたH.264データをアップストリーム
            - 検出人数をアップストリーム
        データチャンク受信のタイムアウト時に計測完了
        """
        try:
            measurement = self.writer.create_measurement("Created by DetectService")
            logging.info(f"Created measurement: {measurement.uuid}")

            await self.downstreamer.open()
            await self.upstreamer.open(measurement.uuid)

            self.decoder.start()
            self.encoder.start()

            basetime_task = asyncio.create_task(
                self.basetime(measurement.uuid)
            )  # 基準時刻設定
            feed_task = asyncio.create_task(self.feed(read_timeout))  # H.264データ供給
            detect_task = asyncio.create_task(self.detect())  # 物体検出
            fetch_task = asyncio.create_task(self.fetch())  # H.264データ取得

            await asyncio.gather(basetime_task, feed_task, detect_task, fetch_task)

        finally:
            self.writer.complete_measurement(measurement.uuid)
            logging.info(f"Completed measurement: {measurement.uuid}")

    async def basetime(self, measurement_uuid: str) -> None:
        """
        基準時刻設定

        自分の計測UUIDは除外（無限ループ回避）

        - メタデータ取得
        - 基準時刻を元計測からコピー
        """
        async for basetime in self.downstreamer.read_basetime():
            logging.info(f"Read basetime {basetime.name} {basetime.base_time}")
            if basetime.session_id == measurement_uuid:
                continue
            await self.upstreamer.send_basetime(basetime)
            logging.info(f"Sent basetime {basetime.name} {basetime.base_time}")

    async def feed(self, read_timeout: float) -> None:
        """
        H.264データ供給

        Args:
            read_timeout (float): ダウンストリームタイムアウト (秒)

        - H.264データダウンストリーム
        - 基準時刻キュー追加
        - デコーダー入力
        """
        async for elapsed_time, frame in self.downstreamer.read(read_timeout):
            logging.info(f"Read elapsed_time {elapsed_time} {len(frame)} bytes")

            await self.elapsed_time_queue.put(elapsed_time)

            await self.decoder.push(frame)

    async def detect(self) -> None:
        """
        物体検出

        - RAWデータ取得
        - 物体検出
        - 検出人数キュー追加
        - エンコーダ入力
        """
        while True:
            frame = await self.decoder.get()

            detected, count = self.detector.detect(frame)

            await self.count_queue.put(count)

            await self.encoder.push(detected)

    async def fetch(self) -> None:
        """
        H.264データ取得

        - エンコードデータ取得
        - H.264データアップストリーム
        - 検出人数アップストリーム
        """

        while True:
            frame = await self.encoder.get()

            elapsed_time = await self.elapsed_time_queue.get()
            count = await self.count_queue.get()

            await self.upstreamer.send(elapsed_time, frame, count)
            logging.info(
                f"Sent elapsed_time {elapsed_time} {len(frame)} bytes {count} persons"
            )

    async def close(self) -> None:
        """
        終了
        """
        self.decoder.stop()
        self.encoder.stop()
        await self.downstreamer.close()
        await self.upstreamer.close()
