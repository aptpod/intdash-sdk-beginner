import asyncio
import json
import logging
from typing import Tuple

import iscp
from chatter.chatter import Chatter
from const.const import DOWN_DATA_NAME_H264
from convertor.convertor import Convertor
from downstreamer.downstreamer import Downstreamer
from openai import RateLimitError
from tiler.tiler import Tiler
from upstreamer.upstreamer import Upstreamer
from writer.measurement_writer import MeasurementWriter


class SummarizeService:
    """
    映像フレーム要約サービス

    H.264ダウンストリーム、グリッド画像化・生成AIによる要約結果アップストリームを管理する

    Attributes:
        downstreamer (Downstreamer): ダウンストリーマー
        decoder (Convertor): デコーダー
        tiler (Tiler): グリッド画像生成
        encoder_preview (Convertor): プレビュー画像エンコーダー
        writer (MeasurementWriter): 計測作成
        upstreamer (Upstreamer): アップストリーマー
        chatter (Chatter): 生成AI問い合わせ
        encoder_summary (Convertor): 要約対象画像エンコーダー
        basetime (iscp.DateTime): 基準時刻
        metadata_queue (Queue): メタデータキュー(相対時刻)
        elapsed_time_queue (Queue): 基準時刻キュー
        prompt_queue (Queue): プロンプトキュー(相対時刻)
        answer_queue (Queue): 要約結果キュー(相対時刻, 回答, 要約対象画像)
    """

    def __init__(
        self,
        downstreamer: Downstreamer,
        decoder: Convertor,
        tiler: Tiler,
        encoder_preview: Convertor,
        writer: MeasurementWriter,
        upstreamer: Upstreamer,
        chatter: Chatter,
        encoder_summary: Convertor,
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
        self.metadata_queue: asyncio.Queue[int] = asyncio.Queue()
        self.elapsed_time_queue: asyncio.Queue[int] = asyncio.Queue()
        self.prompt_queue: asyncio.Queue[int] = asyncio.Queue(maxsize=chat_maxsize)
        self.answer_queue: asyncio.Queue[Tuple[int, str, bytes]] = asyncio.Queue()

    async def start(self, read_timeout: float = 60) -> None:
        """
        開始

        Args:
            read_timeout (float): ダウンストリームタイムアウト (秒)

        要約データ用計測作成
        ダウンストリーム開始、アップストリーム開始
        デコーダー、エンコーダーGstreamerパイプライン開始
        以下を並列実行
        - 基準時刻供給
        - H.264データ供給
            - ダウンストリームしたH.264データをGStreamerデコードパイプラインに渡す
        - グリッド配置
            - デコードされたRAWフレームをOpenCVでグリッド配置
            - グリッド更新：プレビュー用GStreamerエンコードパイプラインに渡す
            - グリッド完成：要約対象GStreamerエンコードパイプラインに渡す
        - プレビュー画像取得
            - エンコードされたプレビュー画像JPEGデータをアップストリーム
        - データ要約
            - OpenAIで画像要約
        - 要約結果データ取得
            - 要約結果をアップストリーム
            - エンコードされた要約対象画像JPEGデータをアップストリーム
        データチャンク受信のタイムアウト時に計測完了
        """
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
                basetime_task,
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
        - メタデータキュー追加
        - デコーダー入力
        """
        async for elapsed_time, name, payload in self.downstreamer.read(read_timeout):
            logging.info(f"Read elapsed {elapsed_time} {name} {len(payload)} bytes")
            if name == DOWN_DATA_NAME_H264:
                await self.metadata_queue.put(elapsed_time)
                await self.decoder.push(payload)

    async def grid(self) -> None:
        """
        グリッド配置

        - RAWデータ取得
        - メタデータキュー取得
        - グリッド配置
        - グリッド更新
          - 経過時間キュー追加
          - プレビュー画像JPEGエンコーダ入力
        - グリッド完成
          - プロンプトキュー追加
          - 要約対象画像JPEGエンコーダ入力
        """
        while True:
            frame = await self.decoder.get()
            elapsed_time = await self.metadata_queue.get()

            absolute_time_unix_nano = self.basetime.unix_nano() + elapsed_time
            absolute_time = iscp.DateTime.from_unix_nano(absolute_time_unix_nano)
            image, filled = self.tiler.tile(frame, absolute_time.datetime)

            if image:
                logging.info("Updated Grid!")
                await self.elapsed_time_queue.put(elapsed_time)
                await self.encoder_preview.push(image)

                if filled:
                    logging.info(f"Filled Grid! {self.prompt_queue.full()}")
                    if self.prompt_queue.full():
                        logging.info("Prompt queue is full!")
                        continue
                    await self.prompt_queue.put(elapsed_time)
                    await self.encoder_summary.push(image)

    async def fetch_preview(self) -> None:
        """
        プレビュー画像データ取得

        - エンコードデータ取得
        - プレビュー画像データアップストリーム
        """

        while True:
            frame = await self.encoder_preview.get()
            elapsed_time = await self.elapsed_time_queue.get()

            await self.upstreamer.send_preview(elapsed_time, frame)
            logging.info(f"Sent elapsed_time {elapsed_time} {len(frame)} bytes")

    async def summarize(self) -> None:
        """
        データ要約

        - プロンプトキュー取得
        - 画像要約
          - RateLimitをオーバーした場合はリトライせず、一定時間スリープ
        - 要約結果キュー追加
        """
        while True:
            elapsed_time = await self.prompt_queue.get()
            frame = await self.encoder_summary.get()

            try:
                answer = await asyncio.to_thread(self.chatter.chat, frame)
                await self.answer_queue.put((elapsed_time, json.dumps(answer), frame))
            except RateLimitError as e:
                logging.info(f"RateLimitError! {e}")
                await asyncio.sleep(0.5)

    async def fetch_answer(self) -> None:
        """
        要約結果データ取得

        - Stringデータ、要約画像データ取得
        - Stringデータアップストリーム
        - 要約対象画像データアップストリーム
        """

        while True:
            elapsed_time, answer, frame = await self.answer_queue.get()

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
