import logging
from typing import AsyncGenerator, Tuple

import iscp


class Downstreamer:
    """
    ダウンストリーマー

    データ受信を管理

    Attributes:
        conn (iscp.Conn): コネクション
        edge_uuid (str): エッジデバイスUUID
    """

    def __init__(self, conn: iscp.Conn, edge_uuid: str) -> None:
        """
        コンストラクタ

        Args:
            conn (iscp.Conn): コネクション
            edge_uuid (str): エッジデバイスUUID
        """
        self.conn = conn
        self.edge_uuid = edge_uuid

    async def open(self) -> None:
        """
        オープン

        H.264映像のIDRフレーム、Non IDRフレームに限定
        """
        self.down = await self.conn.open_downstream(
            filters=[
                iscp.DownstreamFilter(
                    source_node_id=self.edge_uuid,
                    data_filters=[
                        iscp.DataFilter(name="1/h264", type="h264_frame/idr_frame"),
                        iscp.DataFilter(name="1/h264", type="h264_frame/non_idr_frame"),
                    ],
                )
            ],
            omit_empty_chunk=True,
        )

    async def read_basetime(self) -> AsyncGenerator[iscp.BaseTime, None]:
        """
        基準時刻受信

        メタデータを取得して基準時刻を返す

        Yields:
            (BaseTime): 基準時刻
        """
        async for metadata in self.down.metadatas():
            logging.info(f"Received Metadata: {metadata}")
            if isinstance(metadata.metadata, iscp.BaseTime):
                yield metadata.metadata

        raise RuntimeError("Expected metadata not found.")

    async def read(self, timeout: float) -> AsyncGenerator[Tuple[int, bytes], None]:
        """
        データチャンク受信

        Args:
            timeout (float): タイムアウト(秒）

        Yields:
            tuple(int, bytes): 受信したデータポイントの経過時間, ペイロード
        """
        async for msg in self.down.chunks(timeout=timeout):
            for group in msg.data_point_groups:
                for data_point in group.data_points:
                    yield data_point.elapsed_time, data_point.payload

    async def close(self) -> None:
        """
        切断
        """
        await self.conn.close()
