import asyncio
import logging
from typing import Optional

from converter.converter import Converter
from detector.detector import Detector
from downstreamer.downstreamer import Downstreamer
from upstreamer.upstreamer import Upstreamer
from writer.measurement_writer import MeasurementWriter

GST_CLOCK_TIME_NONE = (1 << 64) - 1


class DetectService:
    """
    物体検出サービス

    ダウンストリーム、物体検出、アップストリームを管理する
    H.264データポイントの経過時間はGStreamer BufferのPTSとしてパイプラインへ渡す。
    Fetchステージではエンコード後フレームのPTSを正規化し、検出後H.264と検出人数の
    elapsed_timeとしてアップストリームする。

    Attributes:
        downstreamer (Downstreamer): ダウンストリーマー
        decoder (Converter): デコーダー
        detector (Detector): 物体検出器
        encoder (Converter): エンコーダー
        writer (MeasurementWriter): 計測作成
        upstreamer (Upstreamer): アップストリーマー
        elapsed_time_queue (Queue): 経過時間照合用キュー
        count_queue (Queue): 検出数と検出元PTSのキュー
    """

    def __init__(
        self,
        downstreamer: Downstreamer,
        decoder: Converter,
        detector: Detector,
        encoder: Converter,
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
        self.count_queue: asyncio.Queue[tuple[int, int]] = asyncio.Queue()
        self.encoded_pts_offset: Optional[int] = None

    async def start(self, read_timeout: float = 60) -> None:
        """
        開始

        Args:
            read_timeout (float): ダウンストリームタイムアウト (秒)

        検出後データ用計測作成
        ダウンストリーム開始、アップストリーム開始
        デコーダー、エンコーダーGStreamerパイプライン開始
        以下を並列実行
        - H.264データ供給
            - ダウンストリームした経過時間をPTSとして設定
            - H.264データをGStreamerデコードパイプラインに渡す
        - 物体検出
            - PTS付きRAWフレームをOpenCVで物体検出して矩形描画
            - 検出人数とPTSをキューに追加
            - PTS付きRAWフレームをGStreamerエンコードパイプラインに渡す
        - H.264データ取得
            - エンコードされたH.264データとPTSを取得
            - PTSを正規化して経過時間としてアップストリーム
            - 検出人数をアップストリーム
        元ストリーム終了またはデータチャンク受信のタイムアウト時にEOSを流し、
        decoder/encoder内部に残ったフレームをdrainしてから計測完了
        """
        measurement = None
        basetime_task = None
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

            await asyncio.gather(feed_task, detect_task, fetch_task)

        except TimeoutError:
            pass
        except asyncio.CancelledError:
            pass
        finally:
            if basetime_task is not None:
                basetime_task.cancel()
                await asyncio.gather(basetime_task, return_exceptions=True)
            if measurement is not None:
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
        - 経過時間をPTSとして設定してデコーダー入力
        - 経過時間キュー追加（PTS経路の照合とfallback用）
        """
        try:
            async for elapsed_time, frame in self.downstreamer.read(read_timeout):
                await self.elapsed_time_queue.put(elapsed_time)

                # intdashのelapsed_timeをPTSに載せ、以降はフレーム自身に時刻を持たせる。
                await self.decoder.push(frame, pts=elapsed_time)
        except TimeoutError:
            logging.info("Downstream read timeout. Start decoder drain.")
        finally:
            self.decoder.end_of_stream()

    async def detect(self) -> None:
        """
        物体検出

        - RAWデータ取得
        - 物体検出
        - 検出人数とPTSをキュー追加
        - PTS付きRAWフレームをエンコーダ入力
        """
        try:
            while True:
                frame, pts, _, _ = await self.decoder.get_with_timing()

                detected, count = self.detector.detect(frame)

                # 検出人数はGStreamerには載せず、同じ検出フレームのPTSと一緒にキューで同期する。
                await self.count_queue.put((count, pts))

                encoder_pts = pts if pts != GST_CLOCK_TIME_NONE else None
                await self.encoder.push(detected, pts=encoder_pts)
        except EOFError:
            pass
        finally:
            self.encoder.end_of_stream()

    async def fetch(self) -> None:
        """
        H.264データ取得

        - エンコードデータ取得
        - エンコードPTSを正規化して経過時間に戻す
        - H.264データアップストリーム
        - 検出人数アップストリーム
        """

        try:
            while True:
                frame, pts, _, _ = await self.encoder.get_with_timing()

                queued_elapsed_time = await self.elapsed_time_queue.get()
                count, detected_pts = await self.count_queue.get()
                elapsed_time = queued_elapsed_time
                if pts != GST_CLOCK_TIME_NONE and detected_pts != GST_CLOCK_TIME_NONE:
                    if self.encoded_pts_offset is None:
                        # x264encなどがPTSに固定offsetを加えることがあるため、初回PTS差分で正規化する。
                        self.encoded_pts_offset = pts - detected_pts
                    elapsed_time = pts - self.encoded_pts_offset
                elif detected_pts != GST_CLOCK_TIME_NONE:
                    elapsed_time = detected_pts

                await self.upstreamer.send(elapsed_time, frame, count)
        except EOFError:
            pass

    async def close(self) -> None:
        """
        終了
        """
        self.decoder.stop()
        self.encoder.stop()
        await self.downstreamer.close()
        await self.upstreamer.close()
