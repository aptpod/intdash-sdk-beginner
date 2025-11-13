from pathlib import Path
from typing import BinaryIO, cast

from writer.base_writer import BaseWriter


class BinWriter(BaseWriter[BinaryIO]):
    """
    バイナリファイル出力

    Attributes:
        path (Path): 出力先パス
        _handle (Optional[BinaryIO]): オープン済みファイルハンドル
    """

    def __init__(self, path: Path) -> None:
        super().__init__(path)

    def open_impl(self) -> BinaryIO:
        """オープン"""
        h = open(self.path, "wb")
        return cast(BinaryIO, h)

    def close_impl(self, h: BinaryIO) -> None:
        """クローズ"""
        h.close()

    def write(self, data: bytes) -> None:
        """
        書き出し

        Args:
            data (bytes): 書き出すバイト列
        """
        self.handle.write(data)
