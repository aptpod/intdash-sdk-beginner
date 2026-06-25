import asyncio
import logging
import subprocess
from typing import Callable, Optional

import iscp
from downstreamer.downstreamer import Downstreamer
from logger.delay_logger import DelayLogger


class RtspService:
    """
    RTPSサービス

    ダウンストリーミングおよびRTSPストリーミングを管理する

    Attributes:
        downstreamer (Downstreamer): Downstreamer
        delay_logger (DelayLogger): 遅延ロガー
        rtsp_process_factory (Callable): ffmpegプロセス生成関数
        ffplay_process_factory (Callable): ffplayプロセス生成関数
    """

    def __init__(
        self,
        downstreamer: Downstreamer,
        delay_logger: DelayLogger,
        rtsp_process_factory: Callable[[], subprocess.Popen[bytes]],
        ffplay_process_factory: Callable[[], subprocess.Popen[bytes]],
    ):
        self.downstreamer = downstreamer
        self.delay_logger = delay_logger
        self.rtsp_process_factory = rtsp_process_factory
        self.ffplay_process_factory = ffplay_process_factory
        self.rtsp_process: Optional[subprocess.Popen[bytes]] = None
        self.ffplay_process: Optional[subprocess.Popen[bytes]] = None
        self.current_session_id: Optional[str] = None
        self.waiting_for_idr = True

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
        try:
            await self.downstreamer.open()

            basetime_task = asyncio.create_task(self.basetime())  # 基準時刻設定
            feed_task = asyncio.create_task(self.feed())  # H.264データ供給
            await asyncio.gather(basetime_task, feed_task)

        except asyncio.CancelledError:
            pass

    async def basetime(self) -> None:
        """
        基準時刻設定

        - メタデータ取得
        - 基準時刻を元計測からコピー
        """
        async for session_id, basetime, priority in self.downstreamer.read_basetime():
            logging.info(
                f"Read basetime {basetime} priority {priority} session_id {session_id}"
            )
            self.delay_logger.set_basetime(session_id, basetime, priority)

    async def feed(self) -> None:
        """
        H.264データ供給

        - H.264データダウンストリーム
        - 遅延ロガー出力
        - RTSPストリーム
        - ffplay入力
        """
        async for session_id, is_idr, elapsed_time, frame in self.downstreamer.read():
            self.delay_logger.log(session_id, elapsed_time)

            if session_id != self.current_session_id:
                logging.info(f"Switching media session to {session_id}")
                await self.stop_media_processes()
                self.current_session_id = session_id
                self.waiting_for_idr = True

            if self.media_processes_exited():
                await self.stop_media_processes()
                self.waiting_for_idr = True

            if self.waiting_for_idr:
                if not is_idr:
                    continue
                self.start_media_processes()
                self.waiting_for_idr = False

            try:
                self.write_frame(frame)
            except (BrokenPipeError, OSError) as error:
                logging.warning(f"Media process disconnected: {error}")
                await self.stop_media_processes()
                self.waiting_for_idr = True

    def start_media_processes(self) -> None:
        """FFmpegとffplayを起動する。"""
        logging.info("Starting media processes from an IDR frame")
        self.rtsp_process = self.rtsp_process_factory()
        self.ffplay_process = self.ffplay_process_factory()

    def media_processes_exited(self) -> bool:
        """起動済みプロセスの終了を検出する。"""
        return any(
            process is not None and process.poll() is not None
            for process in (self.rtsp_process, self.ffplay_process)
        )

    def write_frame(self, frame: bytes) -> None:
        """両方のメディアプロセスへフレームを書き込む。"""
        if (
            self.rtsp_process is None
            or self.rtsp_process.stdin is None
            or self.ffplay_process is None
            or self.ffplay_process.stdin is None
        ):
            raise BrokenPipeError("media process stdin is unavailable")
        self.rtsp_process.stdin.write(frame)
        self.ffplay_process.stdin.write(frame)

    async def stop_media_processes(self) -> None:
        """イベントループを止めずにメディアプロセスを停止する。"""
        processes = [
            process
            for process in (self.rtsp_process, self.ffplay_process)
            if process is not None
        ]
        self.rtsp_process = None
        self.ffplay_process = None
        await asyncio.gather(
            *(
                asyncio.to_thread(self.stop_media_process, process)
                for process in processes
            )
        )

    @staticmethod
    def stop_media_process(process: subprocess.Popen[bytes]) -> None:
        """別スレッドで単一のメディアプロセスを停止する。"""
        if process.stdin:
            try:
                process.stdin.close()
            except BrokenPipeError:
                pass
        try:
            process.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    async def close(self) -> None:
        """
        終了
        """
        try:
            await self.downstreamer.close()
        except iscp.ISCPTransportClosedError:
            logging.info("Downstream was already closed")
        finally:
            await self.stop_media_processes()
