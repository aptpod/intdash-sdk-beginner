import asyncio
import logging
from datetime import datetime
from typing import Any, Tuple

import iscp
import psutil
from reader.measurement_reader import MeasurementReader
from upstreamer.upstreamer import Upstreamer
from writer.measurement_writer import MeasurementWriter


class ReplayService:
    """
    計測リプレイサービス

    Attribute:
        reader (MeasurementReader): 計測取得
        writer (MeasurementWriter): 計測作成
        upstreamer (Upstreamer): アップストリーマー
        datapoint_queue (Queue[Any]): データポイントキュー
        speed (float): 再生倍速（speed倍速でリプレイ）
        maxsize (int): キュー最大サイズ
    """

    @staticmethod
    def log_memory_usage() -> None:
        """
        メモリ使用量出力
        """
        process = psutil.Process()
        mem_info = process.memory_info()
        logging.info(f"Memory Usage: {mem_info.rss / 1024 / 1024:.2f} MB")

    def __init__(
        self,
        reader: MeasurementReader,
        writer: MeasurementWriter,
        upstreamer: Upstreamer,
        speed: float = 1,
        maxsize: int = 1000,
    ) -> None:
        self.reader = reader
        self.writer = writer
        self.upstreamer = upstreamer
        self.speed = speed
        self.datapoint_queue: asyncio.Queue[Tuple[int, str, str, Any]] = asyncio.Queue(
            maxsize=maxsize
        )

    async def start(self, read_timeout: float = 60) -> None:
        """
        処理

        Args:
            read_timeout (float): キュー読み込みタイムアウト

        リプレイ用計測作成
        アップストリーム開始
        以下を並列実行
        - データポイント供給
            - REST APIから取得
            - キューに追加
            - キューがいっぱいなら待機
        - データポイント取得
            - キューからデータポイントを取得
            - 経過時間まで待機
            - データポイントをアップストリーム
        取得タイムアウト時に計測完了
        """
        try:
            # 計測作成
            measurement = self.writer.create_measurement("Created by ReplayService")
            logging.info(f"Created measurement: {measurement.uuid}")

            await self.upstreamer.open(measurement.uuid)

            feed_task = asyncio.create_task(
                self.feed(self.reader.get_basetime())
            )  # データポイント供給
            fetch_task = asyncio.create_task(
                self.fetch(measurement.basetime, read_timeout),
            )  # データポイント取得

            await asyncio.gather(feed_task, fetch_task)

        except TimeoutError:
            pass
        except asyncio.CancelledError:
            pass
        finally:
            self.writer.complete_measurement(measurement.uuid)
            logging.info(f"Completed measurement: {measurement.uuid}")

    async def feed(self, basetime: datetime, sleep_time: float = 0.1) -> None:
        """
        データポイント供給

        - REST APIデータポイント取得
        - キュー空き待ち
        - 経過時間算出
        - キュー登録

        Args:
            basetime (datetime): 元計測の基準時刻
            sleep_time (float): キュー待ち時間(秒)
        """
        i = 0
        basetime_ns = int(basetime.timestamp() * 1_000_000) * 1_000

        gen = await asyncio.to_thread(self.reader.get_datapoints)

        for tuple in gen:
            while self.datapoint_queue.full():
                logging.info(f"Queue is full {self.datapoint_queue.qsize()}")
                await asyncio.sleep(sleep_time)

            elapsed_time = tuple[0] - basetime_ns
            type = tuple[1]
            name = tuple[2]
            data = tuple[3]
            await self.datapoint_queue.put((elapsed_time, type, name, data))
            logging.info(f"Put in Queue: {i} {elapsed_time}, {type}, {name}")
            i = i + 1

            ReplayService.log_memory_usage()

    async def fetch(self, basetime: datetime, timeout: float) -> None:
        """
        データポイント取出

        - キューデータ取出
        - 再生倍速調整
          - 経過時間 / speed だけ経過するのを待つ
        - アップストリーム

        Args:
            basetime (int): 元計測の基準時刻
            timeout (float): キュー読み込みタイムアウト

        Raises:
            TimeoutError : キュー読み込みタイムアウト
        """
        i = 0
        basetime_ns = int(basetime.timestamp() * 1_000_000) * 1_000

        # WiP 厳密には計測の基準時刻をあわせるべき
        start_time = iscp.DateTime.utcnow()
        while True:
            elapsed_time, type, name, data = await asyncio.wait_for(
                self.datapoint_queue.get(), timeout
            )

            elapsed_time_speed = int(elapsed_time / self.speed)
            sleep_time = (
                basetime_ns + elapsed_time_speed - iscp.DateTime.utcnow().unix_nano()
            ) / 1_000_000_000

            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

            elapsed_time_replay = (
                iscp.DateTime.utcnow().unix_nano() - start_time.unix_nano()
            )
            await self.upstreamer.send(elapsed_time_replay, type, name, data)
            logging.info(
                f"Sent : {i} {elapsed_time}, {type}, {name} {elapsed_time_replay}"
            )
            i = i + 1

    async def close(self) -> None:
        """
        終了
        """
        await self.upstreamer.close()
