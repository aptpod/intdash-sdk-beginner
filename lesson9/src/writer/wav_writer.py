import wave
from pathlib import Path

from writer.base_writer import BaseWriter


class WavWriter(BaseWriter[wave.Wave_write]):
    """
    WAVファイル出力

    Attributes:
        path (Path): 出力先パス
        _handle (Optional[wave.Wave_write]): オープン済みWAVハンドル
        sr (int): サンプリングレート [Hz]
        nch (int): チャンネル数
        sampwidth_bytes (int): サンプルあたりのバイト数（通常 2 = 16bit）
    """

    def __init__(
        self, path: Path, sr: int = 48000, nch: int = 1, sampwidth_bytes: int = 2
    ) -> None:
        super().__init__(path)
        self.sr = sr
        self.nch = nch
        self.sampwidth_bytes = sampwidth_bytes

    def open_impl(self) -> wave.Wave_write:
        """オープン"""
        h = wave.open(str(self.path), "wb")
        h.setnchannels(self.nch)
        h.setsampwidth(self.sampwidth_bytes)
        h.setframerate(self.sr)
        return h

    def close_impl(self, h: wave.Wave_write) -> None:
        """クローズ"""
        h.close()

    def write(self, data: bytes) -> None:
        """
        書き出し

        Args:
            data (bytes): 書き出すデータ
        """
        h = self.handle
        h.writeframes(data)
