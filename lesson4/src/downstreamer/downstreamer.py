import asyncio
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
        data_name (str): 受信データ名
    """

    def __init__(self, conn: iscp.Conn, edge_uuid: str, data_name: str) -> None:
        """
        コンストラクタ

        Args:
            conn (iscp.Conn): コネクション
            edge_uuid (str): エッジデバイスUUID
            data_name (str): 受信データ名
        """
        self.conn = conn
        self.edge_uuid = edge_uuid
        self.data_name = data_name
        self.upstream_closed = asyncio.Event()

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
                        iscp.DataFilter(name=self.data_name, type="#"),
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
            if isinstance(
                metadata.metadata,
                (iscp.UpstreamNormalClose, iscp.UpstreamAbnormalClose),
            ):
                self.upstream_closed.set()
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
        chunk_iter = self.down.chunks(timeout=timeout).__aiter__()
        close_drain_timeout = 1.0
        while True:
            chunk_task = asyncio.create_task(chunk_iter.__anext__())
            close_task = asyncio.create_task(self.upstream_closed.wait())
            done, pending = await asyncio.wait(
                {chunk_task, close_task},
                return_when=asyncio.FIRST_COMPLETED,
            )

            if chunk_task in done:
                close_task.cancel()
                await asyncio.gather(close_task, return_exceptions=True)
                try:
                    msg = chunk_task.result()
                except StopAsyncIteration:
                    return
            else:
                try:
                    msg = await asyncio.wait_for(
                        chunk_task, timeout=close_drain_timeout
                    )
                except (asyncio.TimeoutError, StopAsyncIteration):
                    logging.info(
                        "Downstream source upstream closed. Stop reading chunks."
                    )
                    return

            for task in pending:
                task.cancel()

            points = []
            for group in msg.data_point_groups:
                for data_point in group.data_points:
                    points.append((data_point.elapsed_time, data_point.payload))

            sorted_points = sorted(points, key=lambda point: point[0])
            for elapsed_time, payload in sorted_points:
                yield elapsed_time, payload

    async def close(self) -> None:
        """
        切断
        """
        await self.down.close()
