from pathlib import Path
from typing import BinaryIO, Optional

from writer.base_writer import BaseWriter

# 改行コード
_CRLF = b"\r\n"


class SrtWriter(BaseWriter[BinaryIO]):
    """
    SRT字幕ファイル出力クラス

    役割:
        - 時系列データから生成された字幕情報を、SRT形式（CRLF, 最大2行）で逐次書き出す。
        - 各エントリは「インデックス番号」「開始時刻 → 終了時刻」「本文1行目/2行目」「空行」で構成される。
        - 書き出し時に改行コードや丸め誤差を自動補正し、QuickTimeなどのプレーヤーでも互換性を維持。

    特徴:
        - 時刻表記は「HH:MM:SS,mmm」形式で、秒境界の丸め誤差を繰り上がり補正
        - 行内の改行コードは空白に置換して整形
        - 逐次生成を想定

    Attributes:
        path (Path): 出力先SRTファイルパス
        _handle (Optional[BinaryIO]): オープン済みファイルハンドル
        _idx (int): 現在の字幕インデックス（1始まり）
    """

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self._idx = 0

    def open_impl(self) -> BinaryIO:
        """オープン"""
        return open(self.path, "wb")

    def close_impl(self, h: BinaryIO) -> None:
        """クローズ"""
        h.close()

    def write(
        self, t0: float, t1: float, line1: str, line2: Optional[str] = None
    ) -> None:
        """
        書き出し

        - index
        - time range
        - payload
        - blank

        1
        00:00:00,010 --> 00:00:01,023
        Altitude: 0.0 m  Speed: 0.0 km/h
        住所文字列

        Args:
            t0 (float): 開始時刻 [sec]
            t1 (float): 終了時刻 [sec]
            line1 (str): 1行目の字幕テキスト
            line2 (Optional[str]): 2行目の字幕テキスト（省略可）
        """
        if t1 <= t0:
            t1 = t0 + 0.5
        self._idx += 1
        h = self.handle

        # index
        h.write(str(self._idx).encode("utf-8"))
        h.write(_CRLF)
        # time range
        rng = self._fmt(t0) + " --> " + self._fmt(t1)
        h.write(rng.encode("utf-8"))
        h.write(_CRLF)
        # payload
        h.write(self._oneline(line1).encode("utf-8"))
        h.write(_CRLF)
        if line2:
            h.write(self._oneline(line2).encode("utf-8"))
            h.write(_CRLF)
        # blank
        h.write(_CRLF)

    # ---- internal --------------------------------------------------------
    @staticmethod
    def _fmt(ts: float) -> str:
        """
        時刻フォーマット

        秒単位の時刻を SRT の HH:MM:SS,mmm 形式へ変換

        Args:
            ts (float): 秒単位の時刻（負の場合は0.0に補正）
        Returns:
            str: フォーマット済み時刻文字列
        """
        if ts < 0:
            ts = 0.0
        total_ms = int(round(ts * 1000.0))
        h, rem_ms = divmod(total_ms, 3600_000)
        m, rem_ms = divmod(rem_ms, 60_000)
        s, ms = divmod(rem_ms, 1_000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"

    @staticmethod
    def _oneline(text: str) -> str:
        """
        1行化

        改行を空白に置換

        Args:
            text (str): 入力テキスト
        Returns:
            str: 1行化済みテキスト
        """
        return text.replace("\r", " ").replace("\n", " ")
