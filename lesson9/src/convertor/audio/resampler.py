from typing import Optional

import numpy as np


class Resampler:
    """
    リサンプラー

    不規則なモノラル波形を等間隔グリッドへ逐次補間

    Attributes:
        sr_out (float): 出力サンプリングレート [Hz]
        fs_in (float): 入力の名目サンプリングレート [Hz]
        dst_next_time (float): 出力サンプルの次の書き込み位置 [sec]
        last_t (Optional[float]): 直近ブロックの最終サンプル時刻 [sec]
        last_x (Optional[float]): 直近ブロックの最終サンプル値
        _inv_sr_out (float): 出力サンプリング周期（1/sr_out）
        _inv_fs_in (float): 入力サンプリング周期（1/fs_in）
    """

    def __init__(self, sr_out: float = 48_000.0, fs_in: Optional[float] = None) -> None:
        if sr_out <= 0:
            raise ValueError("sr_out must be positive")
        if fs_in is not None and fs_in <= 0:
            raise ValueError("fs_in must be positive when provided")

        self.sr_out = sr_out
        self.fs_in = fs_in if fs_in is not None else sr_out

        # 状態
        self.dst_next_time: float = 0.0  # 次に出す時刻 [sec]（basetime相対）
        self.last_t: Optional[float] = None  # 直近ブロックの最終サンプル時刻
        self.last_x: Optional[float] = None  # 直近ブロックの最終サンプル値

        # 前計算（割り算を避ける）
        self._inv_sr_out = 1.0 / self.sr_out
        self._inv_fs_in = 1.0 / self.fs_in

    def push_block(self, t0: float, y: np.ndarray) -> np.ndarray:
        """
        ブロック入力

        不規則ブロックを入力し、出力グリッドへ補間する。

        Args:
            t0: 計測の基準時刻（basetime）からの、ブロック先頭サンプルの相対時刻 [sec]
            y : 波形（float32, 1D）

        Returns:
            np.ndarray: 等間隔サンプル（float32, 1D）、必要なければ空配列
        """
        if y.size == 0:
            return np.empty(0, dtype=np.float32)

        n = int(y.size)
        t_blk_start = t0
        t_blk_end = t_blk_start + n / self.fs_in

        outs: list[np.ndarray] = []

        # 1) 先行ギャップを無音で埋める
        t_src = t_blk_start + (np.arange(n, dtype=np.float64) / self.fs_in)
        x_src = y.astype(np.float32, copy=False)
        if self.last_t is not None and self.last_x is not None:
            t_src = np.concatenate([[self.last_t], t_src])
            x_src = np.concatenate([[self.last_x], x_src])
        t_dst = self._make_dst_times(t_src[0], t_blk_end)

        # 2) ソース時間列（前ブロック最終点を 1 点だけ前置）
        t_src = t_blk_start + (np.arange(n, dtype=np.float64) * self._inv_fs_in)
        x_src = y.astype(np.float32, copy=False)
        if self.last_t is not None and self.last_x is not None:
            t_src = np.concatenate([[self.last_t], t_src])
            x_src = np.concatenate([[self.last_x], x_src])

        # 3) 当該区間で出力グリッドを生成し、線形補間
        t_dst = self._make_dst_times(t_src[0], t_blk_end)
        if t_dst.size:
            y_out = np.interp(t_dst, t_src, x_src).astype(np.float32)
            outs.append(y_out)
            self.dst_next_time = t_dst[-1] + self._inv_sr_out

        # 4) 次ブロック用に最終サンプルを保持
        self.last_t = t_blk_end
        self.last_x = x_src[-1]

        return np.concatenate(outs) if outs else np.empty(0, dtype=np.float32)

    # ---- internal --------------------------------------------------------
    def _make_dst_times(self, t_start: float, t_end: float) -> np.ndarray:
        """
        グリッド生成

        t_start, t_end の範囲で、dst_next_time から始まる等間隔グリッドを生成する。

        Args:
            t_start: 範囲の開始時刻 [sec]
            t_end:   範囲の終了時刻 [sec]

        Returns:
            np.ndarray: 出力サンプル時刻列（float64, 1D）
        """
        first = max(self.dst_next_time, t_start)
        if t_end <= first:
            return np.empty(0, dtype=np.float64)

        # 微小誤差で1サンプル欠けるのを防ぐためのイプシロン
        span = (t_end - first) * self.sr_out + 1e-12
        n = int(np.floor(span))
        if n <= 0:
            return np.empty(0, dtype=np.float64)

        # 等間隔時刻列
        return first + (np.arange(n, dtype=np.float64) * self._inv_sr_out)
