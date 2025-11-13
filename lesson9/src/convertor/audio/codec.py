import numpy as np


def decode_pcm_s16le(data: bytes) -> np.ndarray:
    """
    PCMデコード

    16bit PCM (Little Endian) を float32 (-1.0～+1.0) に変換。
    空データは長さ0の配列を返す。

    Args:
        data (bytes): PCMデータ

    Returns:
        np.ndarray: 正規化済みfloat32配列（-1.0～+1.0）
    """
    if not data:
        return np.empty(0, dtype=np.float32)
    arr = np.frombuffer(data, dtype="<i2").astype(np.float32)
    return arr / 32768.0


def encode_pcm_s16le(x: np.ndarray) -> bytes:
    """
    PCMエンコード

    float32 (-1.0～+1.0) を 16bit PCM (Little Endian) に量子化。

    Args:
        x (np.ndarray): 正規化済みfloat32配列（-1.0～+1.0）

    Returns:
        bytes: 16bit PCMデータ
    """
    if x.size == 0:
        return b""
    x_clipped = np.clip(x, -1.0, 1.0)
    return (x_clipped * 32767.0).astype("<i2").tobytes()
