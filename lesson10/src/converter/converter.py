import asyncio
import logging
from typing import Optional

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402

Gst.init(None)


class Converter:
    """
    メディアコンバーター

    GStreamerパイプラインに従って、メディアデータをリアルタイム変換する
    入力フレームの経過時間はGst.BufferのPTSとして設定し、変換後サンプルのPTSとして取得する。
    これにより、デコード/エンコードで内部バッファリングが発生してもフレームと時刻の対応を保つ。

    Attributes:
        pipeline (Gst.Pipeline): GStreamerパイプライン
        src (Gst.Element): 入力エレメント
        sink (Gst.Element): 出力エレメント
    """

    def __init__(
        self, pipeline: str, appsrc: str = "src", appsink: str = "sink"
    ) -> None:
        """
        コンストラクタ

        Params:
            pipeline (str): GStreamerパイプライン名
            appsrc (str): 入力エレメント名
            appsink (str): 出力エレメント名
        """
        self.pipeline = Gst.parse_launch(pipeline)
        self.src = self.pipeline.get_by_name(appsrc)
        self.sink = self.pipeline.get_by_name(appsink)

    def start(self) -> None:
        """
        開始
        """
        self.pipeline.set_state(Gst.State.PLAYING)

    def stop(self) -> None:
        """
        パイプライン停止
        """
        self.pipeline.set_state(Gst.State.NULL)

    def end_of_stream(self) -> None:
        """
        入力終了

        appsrcにEOSを送ることで、パイプライン内部に残っているフレームをappsinkから
        読み出せる状態にする。
        """
        retval = self.src.emit("end-of-stream")
        if retval != Gst.FlowReturn.OK:
            logging.error(f"Error sending EOS to appsrc: {retval}")

    async def push(
        self, frame: bytes, pts: Optional[int] = None, duration: Optional[int] = None
    ) -> None:
        """
        フレーム追加

        ptsにはintdashのデータポイント経過時間を設定する。
        GStreamerパイプライン内ではこのPTSをフレーム時刻として引き継ぐ。

        Params:
            frame (bytes): 変換前フレームデータ
            pts (int | None): GStreamer bufferのPTS
            duration (int | None): GStreamer bufferのduration
        """
        buffer = Gst.Buffer.new_allocate(None, len(frame), None)
        buffer.fill(0, frame)
        if pts is not None:
            buffer.pts = pts
        if duration is not None:
            buffer.duration = duration
        retval = self.src.emit("push-buffer", buffer)
        if retval != Gst.FlowReturn.OK:
            logging.error(f"Error pushing buffer to appsrc: {retval}")

    async def get(self) -> bytes:
        """
        フレーム取得

        GStreamerがバッファするため、非同期に読み出して返す。

        Returns:
            bytes: 変換後フレームデータ
        """
        data, _, _, _ = await self.get_with_timing()
        return data

    async def get_with_timing(self) -> tuple[bytes, int, int, int]:
        """
        フレーム取得

        GStreamer sampleのタイムスタンプもあわせて返す。
        EOS到達時はEOFErrorを送出する。
        呼び出し側はEOFErrorを契機に後段パイプラインへEOSを伝搬し、drainを完了する。

        Returns:
            tuple(bytes, int, int, int): 変換後データ、PTS、DTS、duration
        """
        while True:
            sample = await asyncio.to_thread(self.sink.emit, "pull-sample")
            if sample is None:
                raise EOFError("GStreamer pipeline reached EOS.")
            if sample:
                buf = sample.get_buffer()
                result, map_info = buf.map(Gst.MapFlags.READ)
                if result:
                    data = bytes(map_info.data)
                    pts = buf.pts
                    dts = buf.dts
                    duration = buf.duration
                    buf.unmap(map_info)
                    return data, pts, dts, duration
