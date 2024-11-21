import asyncio
import logging
import subprocess

from lesson3.src.downstreamer.downstreamer import Downstreamer
from lesson3.src.logger.delay_logger import DelayLogger


class RtspService:
    """
    RTPSサービス

    ダウンストリーミングおよびRTSPストリーミングを管理する

    Attributes:
        downstreamer (Downstreamer): Downstreamer
        delay_logger (DelayLogger): 遅延ロガー
        rtsp_process (subprocess.Popen): ffmpegプロセス
        ffplay_process (subprocess.Popen): ffplayプロセス
    """

    def __init__(
        self,
        downstreamer: Downstreamer,
        delay_logger: DelayLogger,
        rtsp_process: subprocess.Popen,
        ffplay_process: subprocess.Popen,
    ):
        self.downstreamer = downstreamer
        self.delay_logger = delay_logger
        self.rtsp_process = rtsp_process
        self.ffplay_process = ffplay_process

    async def start(self) -> None:
        """
        開始

        ダウンストリーム開始
        以下を並列実行
        - 基準時刻設定
            - メタデータから基準時刻を取得して遅延ロガーに設定（優先度が高い基準時刻に差し替える）
        - H.264データ供給
            - ダウンストリームしたH.264データの経過時間を遅延ロガーに渡してログ出力
            - ダウンストリームしたH.264データをFFmpeg、ffplayに渡して可視化
        """
        await self.downstreamer.open()

        basetime_task = asyncio.create_task(self.basetime())  # 基準時刻設定
        feed_task = asyncio.create_task(self.feed())  # H.264データ供給
        await asyncio.gather(basetime_task, feed_task)

    async def basetime(self) -> None:
        """
        基準時刻設定

        - メタデータ取得
        - 基準時刻を元計測からコピー
        """
        async for basetime, priority in self.downstreamer.read_basetime():
            logging.info(f"Read basetime {basetime} priority {priority}")
            self.delay_logger.set_basetime(basetime, priority)

    async def feed(self) -> None:
        """
        H.264データ供給

        - H.264データダウンストリーム
        - 遅延ロガー出力
        - RTSPストリーム
        - ffplay入力
        """
        if not self.rtsp_process.stdin or not self.ffplay_process.stdin:
            raise
        async for elapsed_time, frame in self.downstreamer.read():
            self.delay_logger.log(elapsed_time)
            self.rtsp_process.stdin.write(frame)
            self.ffplay_process.stdin.write(frame)

    async def close(self) -> None:
        """
        終了
        """
        await self.downstreamer.close()
        if self.rtsp_process.stdin:
            self.rtsp_process.stdin.close()
        self.rtsp_process.wait()
        if self.ffplay_process.stdin:
            self.ffplay_process.stdin.close()
        self.ffplay_process.wait()
