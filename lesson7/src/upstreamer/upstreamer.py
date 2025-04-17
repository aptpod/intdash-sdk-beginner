import logging

import iscp


class Upstreamer:
    """
    アップストリーマー

    データ送信を管理

    Attributes:
        conn (iscp.Conn): コネクション
    """

    def __init__(self, conn: iscp.Conn):
        """
        コンストラクタ

        Args:
            conn (iscp.Conn): コネクション
        """
        self.conn = conn

    async def open(self, session_id: str) -> None:
        """
        アップストリームオープン

        Args:
            session_id (str): 計測UUID
        """
        self.up = await self.conn.open_upstream(session_id=session_id, persist=True)
        logging.info(f"Opened stream session_id {session_id}")

    async def send(
        self, elapsed_time: int, type: str, name: str, payload: bytes
    ) -> None:
        """
        データポイント送信

        Args:
            elapsed_time (int): データポイントの経過時間
            type (str): データ型名
            name (str): データ名
            payload (bytes): データポイントのペイロード
        """
        await self.up.write_data_points(
            iscp.DataID(name=name, type=type),
            iscp.DataPoint(
                elapsed_time=elapsed_time,
                payload=payload,
            ),
        )
        await self.up.flush()

    async def close(self) -> None:
        """
        切断
        """
        await self.up.close()
