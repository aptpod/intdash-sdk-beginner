import logging
from typing import AsyncGenerator, Tuple

import iscp


class Downstreamer:
    """
    ダウンストリーマー

    intdashサーバーとの接続、データ受信を管理

    Attributes:
        conn (iscp.Conn): コネクション
        edge_uuid (str): エッジデバイスUUID
    """

    def __init__(self, conn: iscp.Conn, edge_uuid: str):
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
        ダウンストリームオープン

        H.264映像のキーフレーム、デルタフレームに限定
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

    async def read_basetime(self) -> AsyncGenerator[Tuple[iscp.DateTime, int], None]:
        """
        基準時刻受信

        メタデータを取得して基準時刻と優先度を返す

        Yields:
            (DateTime, int): 基準時刻, priority
        """
        async for metadata in self.down.metadatas():
            logging.info(f"Received Metadata: {metadata}")
            if not isinstance(metadata.metadata, iscp.BaseTime):
                continue
            yield metadata.metadata.base_time, metadata.metadata.priority

    async def read(self) -> AsyncGenerator[Tuple[int, bytes], None]:
        """
        データチャンク受信

        Yields:
            tuple(int, bytes): 受信したデータポイントの経過時間, ペイロード
        """
        async for msg in self.down.chunks():
            for group in msg.data_point_groups:
                for data_point in group.data_points:
                    yield data_point.elapsed_time, data_point.payload

    async def close(self) -> None:
        """
        ダウンストリーム切断
        """
        await self.down.close()
