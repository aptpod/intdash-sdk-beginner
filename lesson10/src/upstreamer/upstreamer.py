import copy
import logging

import iscp


class Upstreamer:
    """
    アップストリーマー

    データ送信を管理

    Attributes:
        conn (iscp.Conn): コネクション
        data_name_preview (str): 送信データ名（プレビュー画像）
        data_name_summary (str): 送信データ名（要約対象画像）
        data_name_answer (str): 送信データ名（要約結果）
    """

    def __init__(
        self,
        conn: iscp.Conn,
        data_name_preview: str,
        data_name_summary: str,
        data_name_answer: str,
    ):
        self.conn = conn
        self.data_name_preview = data_name_preview
        self.data_name_summary = data_name_summary
        self.data_name_answer = data_name_answer

    async def open(self, session_id: str) -> None:
        """
        アップストリームオープン

        Args:
            session_id (str): 計測UUID
        """
        self.up = await self.conn.open_upstream(session_id=session_id, persist=True)
        logging.info(f"Opened stream session_id {session_id}")

    async def send_basetime(self, basetime_src: iscp.BaseTime) -> None:
        """
        基準時刻送信

        Args:
            basetime (BaseTime): 基準時刻
        """
        basetime = copy.copy(basetime_src)
        basetime.session_id = self.up.session_id
        await self.conn.send_base_time(basetime, persist=True)
        logging.info(
            f"Sent basetime basetime.session_id {basetime.session_id} basetime.name {basetime.name}"
        )

    async def send_preview(self, elapsed_time: int, payload: bytes) -> None:
        """
        プレビュー画像送信

        Args:
            elapsed_time: データポイントの経過時間
            payload: データポイントのペイロード
        """
        await self.up.write_data_points(
            iscp.DataID(name=self.data_name_preview, type="jpeg"),
            iscp.DataPoint(
                elapsed_time=elapsed_time,
                payload=payload,
            ),
        )
        await self.up.flush()

    async def send_summary(self, elapsed_time: int, payload: bytes) -> None:
        """
        要約対象画像送信

        Args:
            elapsed_time: データポイントの経過時間
            payload: データポイントのペイロード
        """
        await self.up.write_data_points(
            iscp.DataID(name=self.data_name_summary, type="jpeg"),
            iscp.DataPoint(
                elapsed_time=elapsed_time,
                payload=payload,
            ),
        )
        await self.up.flush()

    async def send_answer(self, elapsed_time: int, payload: str) -> None:
        """
        要約結果送信

        Args:
            elapsed_time: データポイントの経過時間
            payload: データポイントのペイロード
        """
        await self.up.write_data_points(
            iscp.DataID(name=self.data_name_answer, type="string"),
            iscp.DataPoint(
                elapsed_time=elapsed_time,
                payload=payload.encode("utf-8"),
            ),
        )
        await self.up.flush()

    async def close(self) -> None:
        """
        切断
        """
        await self.up.close()
