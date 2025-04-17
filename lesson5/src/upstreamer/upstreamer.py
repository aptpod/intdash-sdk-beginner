import logging

import iscp


class Upstreamer:
    """
    アップストリーマー

    データ送信を管理

    Attributes:
        conn (iscp.Conn): コネクション
        data_name (str): 送信データ名
    """

    @staticmethod
    def is_idr_frame(encoded_data: bytes) -> bool:
        """
        IDRフレーム判別

        H.264データからNALUタイプを読み取り、IDRフレームかを判別する。
        - 開始コードの次のコードがNAL Unit
            - 開始コードリスト分探す
                - 開始コードが見つからない場合、IDRフレームではない
            - NALUタイプを取得
        - IDRフレーム判定
            - IDRフレーム: SPS(nal_type:7) PPS(nal_type:8) IDR(nal_type:5)が順序通りに存在

        Args:
        Return:
            bool:
                True: IDRフレーム
                False: Non-IDRフレーム、またはSPS/PPS/IDRの順序が満たされない
        """
        nal_start_codes = [b"\x00\x00\x00\x01", b"\x00\x00\x01"]
        current_idx = 0
        sps_found = False
        pps_found = False

        while current_idx < len(encoded_data):
            # 開始コードを探す
            start_idx = -1
            start_code_length = 0

            for start_code in nal_start_codes:
                start_idx = encoded_data.find(start_code, current_idx)
                if start_idx != -1:
                    start_code_length = len(start_code)
                    break

            # 開始コードが見つからなかった場合は終了
            if start_idx == -1:
                break

            # NAL Unitのヘッダ位置
            nalu_header_idx = start_idx + start_code_length
            if nalu_header_idx >= len(encoded_data):
                break

            # NAL Unitタイプを取得
            nalu_header = encoded_data[nalu_header_idx]
            nalu_type = nalu_header & 0x1F

            # IDRフレームの順序判定
            if nalu_type == 7:
                sps_found = True
            elif nalu_type == 8 and sps_found:
                pps_found = True
            elif nalu_type == 5 and sps_found and pps_found:
                return True

            # 次のNAL Unitを探索するためにインデックスを更新
            current_idx = nalu_header_idx + 1

        # 全ての必要なNAL Unitが見つからなかった場合
        return False

    def __init__(self, conn: iscp.Conn, data_name: str):
        """
        コンストラクタ

        Args:
            conn (iscp.Conn): コネクション
            data_name (str): 送信データ名
        """
        self.conn = conn
        self.data_name = data_name

    async def open(self, session_id: str) -> None:
        """
        アップストリームオープン

        Args:
            session_id (str): 計測UUID
        """
        self.up = await self.conn.open_upstream(session_id=session_id, persist=True)
        logging.info(f"Opened stream session_id {session_id}")

    async def send(self, elapsed_time: int, payload: bytes) -> None:
        """
        データポイント送信

        Args:
            elapsed_time: データポイントの経過時間
            payload: データポイントのペイロード
        """
        type = (
            "h264_frame/idr_frame"
            if Upstreamer.is_idr_frame(payload)
            else "h264_frame/non_idr_frame"
        )
        await self.up.write_data_points(
            iscp.DataID(name=self.data_name, type=type),
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
