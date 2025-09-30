import asyncio

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
        sink (Gst.Element): 出力エレメント
    """

    def __init__(self, pipeline: str, appsink: str = "sink") -> None:
        """
        コンストラクタ

        Params:
            pipeline (str): Gstreamerパイプライン名
            src (str): 入力エレメント名
            sink (str): 出力エレメント名
        """
        self.pipeline = Gst.parse_launch(pipeline)
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

    async def fetch(self, size: int) -> list[tuple[int, bytes]]:
        """
        フレーム取得

        Gstreamerがバッファするため、非同期に読み出して返す。

        Args:
            size (int): フェッチサイズ

        Returns:
            list:
              (フレーム時刻(ns), 変換後フレームデータ)
              EOS時は空

        """
        frames: list[tuple[int, bytes]] = []

        while len(frames) < size:
            sample = await asyncio.to_thread(self.sink.emit, "pull-sample")
            if not sample:  # EOS
                break

            buf = sample.get_buffer()
            result, map_info = buf.map(Gst.MapFlags.READ)
            if not result:
                break
            pts = buf.pts
            frames.append((pts, bytes(map_info.data)))
            buf.unmap(map_info)

        return frames
