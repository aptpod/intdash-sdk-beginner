import asyncio
import subprocess
import sys
import time
from pathlib import Path
from typing import AsyncGenerator, Callable, cast

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

import iscp
from src.downstreamer.downstreamer import Downstreamer
from src.logger.delay_logger import DelayLogger
from src.service.rtsp_service import RtspService

Frame = tuple[str, bool, int, bytes]


class FakeStdin:
    def __init__(self) -> None:
        self.data = bytearray()

    def write(self, data: bytes) -> int:
        self.data.extend(data)
        return len(data)

    def close(self) -> None:
        pass

    def getvalue(self) -> bytes:
        return bytes(self.data)


class BrokenOnSecondWriteStdin(FakeStdin):
    def __init__(self) -> None:
        super().__init__()
        self.write_count = 0

    def write(self, data: bytes) -> int:
        self.write_count += 1
        if self.write_count == 2:
            raise BrokenPipeError("test disconnect")
        return super().write(data)


class FakeProcess:
    def __init__(self, stdin: FakeStdin | None = None) -> None:
        self.stdin = stdin or FakeStdin()
        self.returncode: int | None = None

    def poll(self) -> int | None:
        return self.returncode

    def wait(self, timeout: float | None = None) -> int:
        self.returncode = 0
        return self.returncode


class SlowFakeProcess(FakeProcess):
    def wait(self, timeout: float | None = None) -> int:
        time.sleep(0.1)
        return super().wait(timeout)


class FakeDownstreamer:
    def __init__(self, items: tuple[Frame, ...] | None = None) -> None:
        self.items = items or (
            ("session-1", False, 0, b"delta-1"),
            ("session-1", True, 1, b"idr-1"),
            ("session-1", False, 2, b"delta-2"),
            ("session-2", False, 0, b"delta-3"),
            ("session-2", True, 1, b"idr-2"),
        )

    async def read(self) -> AsyncGenerator[Frame, None]:
        for item in self.items:
            yield item


class FakeDelayLogger:
    def log(self, session_id: str, elapsed_time: int) -> None:
        pass


def test_feed_restarts_processes_from_idr_on_session_change() -> None:
    rtsp_processes: list[FakeProcess] = []
    ffplay_processes: list[FakeProcess] = []

    def make_process(processes: list[FakeProcess]) -> FakeProcess:
        process = FakeProcess()
        processes.append(process)
        return process

    service = RtspService(
        cast(Downstreamer, FakeDownstreamer()),
        cast(DelayLogger, FakeDelayLogger()),
        cast(
            Callable[[], subprocess.Popen[bytes]],
            lambda: make_process(rtsp_processes),
        ),
        cast(
            Callable[[], subprocess.Popen[bytes]],
            lambda: make_process(ffplay_processes),
        ),
    )

    asyncio.run(service.feed())

    assert len(rtsp_processes) == 2
    assert len(ffplay_processes) == 2
    assert rtsp_processes[0].stdin.getvalue() == b"idr-1delta-2"
    assert rtsp_processes[1].stdin.getvalue() == b"idr-2"
    assert service.current_session_id == "session-2"
    assert not service.waiting_for_idr


def test_feed_recovers_from_broken_pipe_at_next_idr() -> None:
    frames: tuple[Frame, ...] = (
        ("session-1", True, 0, b"idr-1"),
        ("session-1", False, 1, b"broken-delta"),
        ("session-1", False, 2, b"skipped-delta"),
        ("session-1", True, 3, b"idr-2"),
    )
    rtsp_processes: list[FakeProcess] = []

    def make_rtsp() -> FakeProcess:
        stdin = BrokenOnSecondWriteStdin() if not rtsp_processes else FakeStdin()
        process = FakeProcess(stdin)
        rtsp_processes.append(process)
        return process

    service = RtspService(
        cast(Downstreamer, FakeDownstreamer(frames)),
        cast(DelayLogger, FakeDelayLogger()),
        cast(Callable[[], subprocess.Popen[bytes]], make_rtsp),
        cast(Callable[[], subprocess.Popen[bytes]], FakeProcess),
    )

    asyncio.run(service.feed())

    assert len(rtsp_processes) == 2
    assert rtsp_processes[0].stdin.getvalue() == b"idr-1"
    assert rtsp_processes[1].stdin.getvalue() == b"idr-2"


def test_delay_logger_keeps_priority_per_session() -> None:
    logger = DelayLogger(9)
    session_1_low = iscp.DateTime.utcnow()
    session_1_high = iscp.DateTime.utcnow()
    session_2_low = iscp.DateTime.utcnow()

    logger.set_basetime("session-1", session_1_low, 20)
    logger.set_basetime("session-1", session_1_high, 40)
    logger.set_basetime("session-1", session_1_low, 20)
    logger.set_basetime("session-2", session_2_low, 20)

    assert logger.basetimes["session-1"] == (session_1_high, 40)
    assert logger.basetimes["session-2"] == (session_2_low, 20)


def test_stopping_processes_does_not_block_event_loop() -> None:
    service = RtspService(
        cast(Downstreamer, FakeDownstreamer()),
        cast(DelayLogger, FakeDelayLogger()),
        cast(Callable[[], subprocess.Popen[bytes]], FakeProcess),
        cast(Callable[[], subprocess.Popen[bytes]], FakeProcess),
    )
    service.rtsp_process = cast(subprocess.Popen[bytes], SlowFakeProcess())
    service.ffplay_process = cast(subprocess.Popen[bytes], SlowFakeProcess())

    async def verify() -> None:
        stop_task = asyncio.create_task(service.stop_media_processes())
        await asyncio.sleep(0.01)
        assert not stop_task.done()
        await stop_task

    asyncio.run(verify())
