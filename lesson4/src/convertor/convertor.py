import asyncio
import logging

import gi

gi.require_version("Gst", "1.0")
from gi.repository import Gst  # noqa: E402

Gst.init(None)


class Convertor:
    """
    メディアコンバーター

    Gstreamerパイプラインに従って、メディアデータをリアルタイム変換する

    Attributes:
        pipeline (Gst.Pipeline): Gstreamerパイプライン
        src (Gst.Element): 入力エレメント
        sink (Gst.Element): 出力エレメント
    """

    def __init__(
        self, pipeline: str, appsrc: str = "src", appsink: str = "sink"
    ) -> None:
        """
        コンストラクタ

        Params:
            pipeline (str): Gstreamerパイプライン名
            src (str): 入力エレメント名
            sink (str): 出力エレメント名
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

    async def push(self, frame: bytes) -> None:
        """
        フレーム追加

        Params:
            frame (bytes): 変換前フレームデータ
        """
        buffer = Gst.Buffer.new_allocate(None, len(frame), None)
        buffer.fill(0, frame)
        retval = self.src.emit("push-buffer", buffer)
        if retval != Gst.FlowReturn.OK:
            logging.error(f"Error pushing buffer to appsrc: {retval}")

    async def get(self) -> bytes:
        """
        フレーム取得

        Gstreamerがバッファするため、非同期に読み出して返す。

        Returns:
            bytes: 変換後フレームデータ
        """
        while True:
            sample = await asyncio.to_thread(self.sink.emit, "pull-sample")
            if sample:
                buf = sample.get_buffer()
                result, map_info = buf.map(Gst.MapFlags.READ)
                if result:
                    data = map_info.data
                    buf.unmap(map_info)
                    return data
