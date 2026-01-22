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
        data_name (list): 受信データ名
    """

    def __init__(self, conn: iscp.Conn, edge_uuid: str, data_name: list) -> None:
        """
        コンストラクタ

        Args:
            conn (iscp.Conn): コネクション
            edge_uuid (str): エッジデバイスUUID
            data_name (list): 受信データ名
        """
        self.conn = conn
        self.edge_uuid = edge_uuid
        self.data_name = data_name

    async def open(self) -> None:
        """
        オープン

        H.264映像のIDRフレーム、Non IDRフレームに限定
        """
        data_filters = []
        for name in self.data_name:
            data_filters.append(iscp.DataFilter(name=name, type="#"))

        self.down = await self.conn.open_downstream(
            filters=[
                iscp.DownstreamFilter(
                    source_node_id=self.edge_uuid,
                    data_filters=data_filters,
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

    async def read(
        self, timeout: float
    ) -> AsyncGenerator[Tuple[int, str, bytes], None]:
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
                    yield (
                        data_point.elapsed_time,
                        group.data_id.name,
                        data_point.payload,
                    )

    async def close(self) -> None:
        """
        切断
        """
        await self.down.close()
