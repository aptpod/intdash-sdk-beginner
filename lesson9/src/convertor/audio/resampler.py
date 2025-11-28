from typing import Optional

import numpy as np


class Resampler:
    """
    リサンプラー

    不規則に到着するモノラル波形ブロックを、指定のサンプリングレートに
    従った等間隔グリッド上に逐次並べる。

    - 入力ブロックは [計測の基準時刻 からの相対時刻 t0] と [波形 y] の組
    - ブロック間に時間的ギャップがある場合は、0.0 で無音補完する
    - 各ブロック内部は、名目サンプリングレート fs_in に従うと仮定し、
      前ブロック末尾 1 点を含めて線形補間する

    前提:
        - t0 は単調増加（過去に戻らない）
        - y は 1D の float32 配列（呼び出し側でデコード済み）

    Attributes:
        sr_out (float): 出力サンプリングレート [Hz]
        fs_in (float): 入力の名目サンプリングレート [Hz]
        dst_next_time (float): 次に出力すべきサンプルの時刻 [sec]（basetime 相対）
        last_t (Optional[float]): 直近ブロックの「最終サンプル時刻」 [sec]（basetime 相対）
        last_x (Optional[float]):  直近ブロックの「最終サンプル値」
        _inv_sr_out (float): 出力サンプリング周期（1 / sr_out）
        _inv_fs_in (float): 入力サンプリング周期（1 / fs_in）
    """

    def __init__(self, sr_out: float = 48_000.0, fs_in: Optional[float] = None) -> None:
        if sr_out <= 0:
            raise ValueError("sr_out must be positive")
        if fs_in is not None and fs_in <= 0:
            raise ValueError("fs_in must be positive when provided")

        self.sr_out = float(sr_out)
        self.fs_in = float(fs_in) if fs_in is not None else float(sr_out)

        # 状態（逐次処理で持ち回り）
        self.dst_next_time: float = 0.0
        self.last_t: Optional[float] = None
        self.last_x: Optional[float] = None

        # 前計算（毎サンプルの割り算を避ける）
        self._inv_sr_out = 1.0 / self.sr_out
        self._inv_fs_in = 1.0 / self.fs_in

    def push_block(self, t0: float, y: np.ndarray) -> np.ndarray:
        """
        ブロック入力

        1ブロック分の波形を入力し、必要な分だけ等間隔グリッド上のサンプルを返す。
        ブロック間にギャップがある場合は、0.0 で無音サンプルを挿入する。

        Args:
            t0 (float): 計測の基準時刻（basetime）からこのブロック先頭サンプルの相対時刻 [sec]
            y (np.ndarray): モノラルPCM（float32, 1D）

        Returns:
            np.ndarray:
                出力サンプリングレート sr_out に揃えた等間隔サンプル（float32, 1D）。
                このブロックで新たに生成されたサンプルのみを返す。
                何も出力しない場合は長さ 0 の配列。
        """
        if y.size == 0:
            return np.empty(0, dtype=np.float32)

        outs: list[np.ndarray] = []

        # 1) ブロック全体の時間範囲を計算
        t_blk_start = t0
        t_blk_end = t_blk_start + y.size * self._inv_fs_in

        # 2) 直前の出力位置から今回ブロックまでギャップがあれば 0 埋めで補完
        if self.last_t is not None:
            if self.dst_next_time < t_blk_start:
                # [dst_next_time, t_blk_start) を等間隔グリッドにし、その本数だけ 0 を吐く
                t_gap = self._make_dst_times(self.dst_next_time, t_blk_start)
                if t_gap.size:
                    outs.append(np.zeros(t_gap.size, dtype=np.float32))
                    # 次に出力すべき位置を更新
                    self.dst_next_time = float(t_gap[-1]) + self._inv_sr_out

        # 3) 補間対象のソース時刻列 / 値列を構築
        #    今回ブロックの時刻は fs_in に従うと仮定し、
        #    必要に応じて「前ブロックの最終点」を 1 点前置して連続性を保つ
        t_src = t_blk_start + (np.arange(y.size, dtype=np.float64) * self._inv_fs_in)
        x_src = y.astype(np.float32, copy=False)
        if self.last_t is not None and self.last_x is not None:
            t_src = np.concatenate([[self.last_t], t_src])
            x_src = np.concatenate([[self.last_x], x_src])

        # 4) [t_src[0], t_blk_end) の範囲で出力グリッドを作り、線形補間
        t_dst = self._make_dst_times(t_src[0], t_blk_end)
        if t_dst.size:
            # np.interp: t_src は単調増加前提
            y_out = np.interp(t_dst, t_src, x_src).astype(np.float32)
            outs.append(y_out)
            self.dst_next_time = float(t_dst[-1]) + self._inv_sr_out

        # 5) 次ブロック用に、今回ブロックの最終サンプル情報を保持
        self.last_t = t_blk_end
        self.last_x = x_src[-1]

        return np.concatenate(outs) if outs else np.empty(0, dtype=np.float32)

    # ---- internal --------------------------------------------------------
    def _make_dst_times(self, t_start: float, t_end: float) -> np.ndarray:
        """
        出力グリッド生成

        現在の dst_next_time 以降で、[t_start, t_end) をカバーする
        等間隔サンプル時刻列を生成する。

        - 実際には max(dst_next_time, t_start) から開始する
        - t_end に達するまで sr_out 間隔で刻み続ける

        Args:
            t_start (float): 範囲の開始時刻 [sec]
            t_end   (float): 範囲の終了時刻 [sec]

        Returns:
            np.ndarray:
                出力サンプル時刻列（float64, 1D）。
                生成できない場合は長さ 0 の配列。
        """
        # 次に出力すべき位置と、要求範囲の開始のうち「後ろ側」を採用
        first = max(self.dst_next_time, t_start)
        if t_end <= first:
            return np.empty(0, dtype=np.float64)

        # 微小な浮動小数誤差で 1 サンプル欠けるのを避けるためのイプシロン
        span = (t_end - first) * self.sr_out + 1e-12
        n = int(np.floor(span))
        if n <= 0:
            return np.empty(0, dtype=np.float64)

        # 等間隔時刻列を生成
        return first + (np.arange(n, dtype=np.float64) * self._inv_sr_out)
