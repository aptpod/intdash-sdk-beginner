import asyncio
import json
import logging
from typing import Optional, Tuple

import iscp
from chatter.chatter import Chatter
from const.const import DOWN_DATA_NAME_H264
from converter.converter import Converter
from downstreamer.downstreamer import Downstreamer
from openai import RateLimitError
from tiler.tiler import Tiler
from upstreamer.upstreamer import Upstreamer
from writer.measurement_writer import MeasurementWriter

GST_CLOCK_TIME_NONE = (1 << 64) - 1


class SummarizeService:
    """
    映像フレーム要約サービス

    H.264ダウンストリーム、グリッド画像化・生成AIによる要約結果アップストリームを管理する
    H.264データポイントの経過時間はGStreamer BufferのPTSとしてパイプラインへ渡す。
    プレビュー画像、要約対象画像、要約結果は、エンコード後フレームのPTSを正規化した
    elapsed_timeでアップストリームする。

    Attributes:
        downstreamer (Downstreamer): ダウンストリーマー
        decoder (Converter): デコーダー
        tiler (Tiler): グリッド画像生成
        encoder_preview (Converter): プレビュー画像エンコーダー
        writer (MeasurementWriter): 計測作成
        upstreamer (Upstreamer): アップストリーマー
        chatter (Chatter): 生成AI問い合わせ
        encoder_summary (Converter): 要約対象画像エンコーダー
        basetime (iscp.DateTime): 基準時刻
        metadata_queue (Queue): デコードPTS照合用キュー
        elapsed_time_queue (Queue): プレビュー画像PTS照合用キュー
        prompt_queue (Queue): プロンプトキュー(要約対象画像PTS照合用)
        answer_queue (Queue): 要約結果キュー(相対時刻, 回答, 要約対象画像)
    """

    def __init__(
        self,
        downstreamer: Downstreamer,
        decoder: Converter,
        tiler: Tiler,
        encoder_preview: Converter,
        writer: MeasurementWriter,
        upstreamer: Upstreamer,
        chatter: Chatter,
        encoder_summary: Converter,
        chat_maxsize: int = 2,
    ) -> None:
        self.downstreamer = downstreamer
        self.decoder = decoder
        self.tiler = tiler
        self.encoder_preview = encoder_preview
        self.writer = writer
        self.upstreamer = upstreamer
        self.chatter = chatter
        self.encoder_summary = encoder_summary

        self.basetime: iscp.DateTime = iscp.DateTime.utcnow()
        self.metadata_queue: asyncio.Queue[Tuple[int, int]] = asyncio.Queue()
        self.elapsed_time_queue: asyncio.Queue[Tuple[int, int]] = asyncio.Queue()
        self.prompt_queue: asyncio.Queue[Optional[int]] = asyncio.Queue(
            maxsize=chat_maxsize
        )
        self.answer_queue: asyncio.Queue[
            Tuple[Optional[int], Optional[str], Optional[bytes]]
        ] = asyncio.Queue()
        self.read_seq = 0
        self.decoded_seq = 0
        self.preview_seq = 0
        self.summary_seq = 0
        self.preview_pts_offset: Optional[int] = None
        self.summary_pts_offset: Optional[int] = None

    async def start(self, read_timeout: float = 60) -> None:
        """
        開始

        Args:
            read_timeout (float): ダウンストリームタイムアウト (秒)

        要約データ用計測作成
        ダウンストリーム開始、アップストリーム開始
        デコーダー、エンコーダーGStreamerパイプライン開始
        以下を並列実行
        - 基準時刻供給
        - H.264データ供給
            - ダウンストリームした経過時間をPTSとして設定
            - H.264データをGStreamerデコードパイプラインに渡す
        - グリッド配置
            - PTS付きRAWフレームをOpenCVでグリッド配置
            - グリッド更新：PTS付きでプレビュー用GStreamerエンコードパイプラインに渡す
            - グリッド完成：PTS付きで要約対象GStreamerエンコードパイプラインに渡す
        - プレビュー画像取得
            - エンコードされたプレビュー画像JPEGデータとPTSを取得
            - PTSを正規化して経過時間としてアップストリーム
        - データ要約
            - エンコードされた要約対象画像JPEGデータとPTSを取得
            - OpenAIで画像要約
        - 要約結果データ取得
            - 要約結果をアップストリーム
            - エンコードされた要約対象画像JPEGデータをアップストリーム
        元ストリーム終了またはデータチャンク受信のタイムアウト時にEOSを流し、
        decoder/encoder内部に残ったフレームをdrainしてから計測完了
        """
        measurement = None
        basetime_task = None
        try:
            measurement = self.writer.create_measurement("Created by SummarizeService")
            logging.info(f"Created measurement: {measurement.uuid}")

            await self.downstreamer.open()
            await self.upstreamer.open(measurement.uuid)

            self.decoder.start()
            self.encoder_preview.start()
            self.encoder_summary.start()

            basetime_task = asyncio.create_task(
                self.feed_basetime(measurement.uuid)
            )  # 基準時刻設定
            feed_task = asyncio.create_task(self.feed(read_timeout))  # H.264データ供給
            grid_task = asyncio.create_task(self.grid())  # グリッド配置
            fetch_preview_task = asyncio.create_task(
                self.fetch_preview()
            )  # グリッド画像取得
            summarize_task = asyncio.create_task(self.summarize())  # データ要約
            fetch_answer_task = asyncio.create_task(
                self.fetch_answer()
            )  # 要約結果データ取得

            await asyncio.gather(
                feed_task,
                grid_task,
                fetch_preview_task,
                summarize_task,
                fetch_answer_task,
            )

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

    async def feed_basetime(self, measurement_uuid: str) -> None:
        """
        基準時刻供給

        自分の計測UUIDは除外（無限ループ回避）

        - メタデータ取得
        - 基準時刻を元計測からコピー
        - グリッド表示のために基準時刻を保持
        """
        async for basetime in self.downstreamer.read_basetime():
            logging.info(f"Read basetime {basetime.name} {basetime.base_time}")
            if basetime.session_id == measurement_uuid:
                continue
            await self.upstreamer.send_basetime(basetime)
            logging.info(f"Sent basetime {basetime.name} {basetime.base_time}")

            self.basetime = basetime.base_time

    async def feed(self, read_timeout: float) -> None:
        """
        H.264データ供給

        Args:
            read_timeout (float): ダウンストリームタイムアウト (秒)

        - 緯度経度・速度を集約
        - H.264データダウンストリーム
        - 経過時間をPTSとして設定してデコーダー入力
        - メタデータキュー追加（PTS経路の照合とfallback用）
        """
        try:
            async for elapsed_time, name, payload in self.downstreamer.read(
                read_timeout
            ):
                logging.info(f"Read elapsed {elapsed_time} {name} {len(payload)} bytes")
                if name == DOWN_DATA_NAME_H264:
                    self.read_seq += 1
                    await self.metadata_queue.put((self.read_seq, elapsed_time))
                    await self.decoder.push(payload, pts=elapsed_time)
        except TimeoutError:
            logging.info("Downstream read timeout. Start decoder drain.")
        finally:
            logging.info(
                "Trace feed_eos read_seq=%d metadata_q=%d preview_q=%d prompt_q=%d",
                self.read_seq,
                self.metadata_queue.qsize(),
                self.elapsed_time_queue.qsize(),
                self.prompt_queue.qsize(),
            )
            self.decoder.end_of_stream()

    async def grid(self) -> None:
        """
        グリッド配置

        - RAWデータ取得
        - デコードPTS取得
        - グリッド配置
        - グリッド更新
          - PTS付きプレビュー画像JPEGエンコーダ入力
        - グリッド完成
          - プロンプトキュー追加
          - PTS付き要約対象画像JPEGエンコーダ入力
        """
        try:
            while True:
                frame, pts, _, _ = await self.decoder.get_with_timing()
                self.decoded_seq += 1
                _, queued_elapsed_time = await self.metadata_queue.get()
                elapsed_time = queued_elapsed_time
                if pts != GST_CLOCK_TIME_NONE:
                    elapsed_time = pts
                if elapsed_time != queued_elapsed_time:
                    logging.info(
                        "Trace decoded_elapsed_mismatch decoded_seq=%d queued_elapsed_time=%d selected_elapsed_time=%d",
                        self.decoded_seq,
                        queued_elapsed_time,
                        elapsed_time,
                    )

                absolute_time_unix_nano = self.basetime.unix_nano() + elapsed_time
                absolute_time = iscp.DateTime.from_unix_nano(absolute_time_unix_nano)
                image, filled = self.tiler.tile(frame, absolute_time.datetime)

                if image:
                    logging.info("Updated Grid!")
                    self.preview_seq += 1
                    await self.elapsed_time_queue.put(
                        (self.preview_seq, elapsed_time)
                    )
                    await self.encoder_preview.push(image, pts=elapsed_time)

                    if filled:
                        logging.info(f"Filled Grid! {self.prompt_queue.full()}")
                        if self.prompt_queue.full():
                            logging.info("Prompt queue is full!")
                            continue
                        await self.prompt_queue.put(elapsed_time)
                        await self.encoder_summary.push(image, pts=elapsed_time)
        except EOFError:
            logging.info("Decoder drained. Start JPEG encoder drain.")
        finally:
            logging.info(
                "Trace grid_eos decoded_seq=%d preview_seq=%d summary_q=%d",
                self.decoded_seq,
                self.preview_seq,
                self.prompt_queue.qsize(),
            )
            self.encoder_preview.end_of_stream()
            self.encoder_summary.end_of_stream()
            await self.prompt_queue.put(None)

    async def fetch_preview(self) -> None:
        """
        プレビュー画像データ取得

        - エンコードデータ取得
        - プレビュー画像データアップストリーム
        """

        try:
            while True:
                frame, pts, _, _ = await self.encoder_preview.get_with_timing()
                preview_seq, queued_elapsed_time = await self.elapsed_time_queue.get()
                elapsed_time = queued_elapsed_time
                if pts != GST_CLOCK_TIME_NONE:
                    if self.preview_pts_offset is None:
                        self.preview_pts_offset = pts - queued_elapsed_time
                        logging.info(
                            "Trace preview_pts_offset offset=%d first_encoded_pts=%d first_source_pts=%d",
                            self.preview_pts_offset,
                            pts,
                            queued_elapsed_time,
                        )
                    elapsed_time = pts - self.preview_pts_offset
                if elapsed_time != queued_elapsed_time:
                    logging.info(
                        "Trace preview_elapsed_mismatch preview_seq=%d queued_elapsed_time=%d selected_elapsed_time=%d",
                        preview_seq,
                        queued_elapsed_time,
                        elapsed_time,
                    )

                await self.upstreamer.send_preview(elapsed_time, frame)
                logging.info(f"Sent elapsed_time {elapsed_time} {len(frame)} bytes")
        except EOFError:
            logging.info("Preview encoder drained.")

    async def summarize(self) -> None:
        """
        データ要約

        - プロンプトキュー取得
        - 画像要約
          - RateLimitをオーバーした場合はリトライせず、一定時間スリープ
        - 要約結果キュー追加
        """
        try:
            while True:
                queued_elapsed_time = await self.prompt_queue.get()
                if queued_elapsed_time is None:
                    break
                frame, pts, _, _ = await self.encoder_summary.get_with_timing()
                self.summary_seq += 1
                elapsed_time = queued_elapsed_time
                if pts != GST_CLOCK_TIME_NONE:
                    if self.summary_pts_offset is None:
                        self.summary_pts_offset = pts - queued_elapsed_time
                        logging.info(
                            "Trace summary_pts_offset offset=%d first_encoded_pts=%d first_source_pts=%d",
                            self.summary_pts_offset,
                            pts,
                            queued_elapsed_time,
                        )
                    elapsed_time = pts - self.summary_pts_offset
                if elapsed_time != queued_elapsed_time:
                    logging.info(
                        "Trace summary_elapsed_mismatch summary_seq=%d queued_elapsed_time=%d selected_elapsed_time=%d",
                        self.summary_seq,
                        queued_elapsed_time,
                        elapsed_time,
                    )

                try:
                    answer = await asyncio.to_thread(self.chatter.chat, frame)
                    await self.answer_queue.put(
                        (elapsed_time, json.dumps(answer), frame)
                    )
                except RateLimitError as e:
                    logging.info(f"RateLimitError! {e}")
                    await asyncio.sleep(0.5)
        except EOFError:
            logging.info("Summary encoder reached EOS.")
        finally:
            logging.info("Summary encoder drained.")
            await self.answer_queue.put((None, None, None))

    async def fetch_answer(self) -> None:
        """
        要約結果データ取得

        - Stringデータ、要約画像データ取得
        - Stringデータアップストリーム
        - 要約対象画像データアップストリーム
        """

        while True:
            elapsed_time, answer, frame = await self.answer_queue.get()
            if elapsed_time is None or answer is None or frame is None:
                break

            await self.upstreamer.send_answer(elapsed_time, answer)
            await self.upstreamer.send_summary(elapsed_time, frame)
            logging.info(
                f"Sent elapsed_time {elapsed_time} answer {answer} {len(frame)} bytes"
            )

    async def close(self) -> None:
        """
        終了
        """
        self.decoder.stop()
        self.encoder_preview.stop()
        self.encoder_summary.stop()
        await self.downstreamer.close()
        await self.upstreamer.close()
