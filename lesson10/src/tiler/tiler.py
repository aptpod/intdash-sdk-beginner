from datetime import datetime
from typing import List, Optional

import cv2
import numpy as np
from const.const import (
    DIFF_THRESHOLD,
    FLUSH_TIMEOUT,
    GRID,
    TEXT_COLOR,
    TEXT_FONT,
    TEXT_OFFSET,
    TEXT_SCALE,
    TEXT_THICK,
)


class Tiler:
    """
    グリッド画像生成

    映像フレーム（デコード済みBGR bytes）から場面変化を検出し、
    変化したフレームだけをタイルとして
    時系列に m x n に配置したグリッド画像を返す。

    - 各タイルには "hh:mm:ss.SSS" をオーバーレイする
    - グリッド完成(m x nが埋まる）か出力フレームタイムアウトで、グリッドを flush して内部状態をリセットする
    - 返す画像は BGR の生bytes

    Attributes:
        _in_w (int): 入力フレーム幅
        _in_h (int): 入力フレーム高さ
        _cols (int): 出力フレームグリッド列数
        _rows (int): 出力フレームグリッド行数
        _grid_size (int): 出力フレームグリッド数
        _tile_w (int): 出力タイル幅
        _tile_h (int): 出力タイル高さ
        _diff_tile_hreshold (float): 前フレームヒストグラム差分判定
        _flush_timeout (float): 出力フレームタイムアウト値
        _tiles (List): 出力タイル画像リスト
        _prev_tile_hist (ndarray): 前回出力タイル画像ヒストグラム
        _grid_started_at (datetime): グリッド開始時刻
    """

    def __init__(
        self,
        in_w: int,
        in_h: int,
        out_w: Optional[int] = None,
        out_h: Optional[int] = None,
        *,
        cols: int = GRID[0],
        rows: int = GRID[1],
        diff_tile_hreshold: float = DIFF_THRESHOLD,
        flush_timeout: float = FLUSH_TIMEOUT,
    ) -> None:
        self._in_w = in_w
        self._in_h = in_h
        _out_w = out_w if out_w is not None else in_w
        _out_h = out_h if out_h is not None else in_h

        # グリッド
        self._rows = rows
        self._cols = cols
        self._grid_size = rows * cols
        self._tile_w = _out_w // self._cols
        self._tile_h = _out_h // self._rows
        if self._tile_w * self._cols != _out_w or self._tile_h * self._rows != _out_h:
            raise ValueError(
                f"out size must be divisible by grid. out=({_out_w},{_out_h}) grid=({self._rows}x{self._cols})"
            )

        self._diff_threshold = diff_tile_hreshold
        self._flush_timeout = flush_timeout

        self._tiles: List[np.ndarray] = []
        self._prev_tile_hist: Optional[np.ndarray] = None
        self._grid_started_at: Optional[datetime] = None

    def tile(self, frame: bytes, ts: datetime) -> tuple[Optional[bytes], bool]:
        """
        フレーム差分判定・グリッド配置

        - 入力フレームサイズチェック
        - フレーム縮小
        - タイムスタンプオーバーレイ
        - 出力フレームタイムアウトチェック
            - グリッド画像完成
            - 内部状態をリセット
            - タイルを次グリッドの1枚目にする
        - フレーム差分判定
        - 出力タイル画像リスト追加
        - グリッド画像生成
        - 完成判定

        Args:
            frame (bytes): デコード済みBGRフレーム
            ts (datetime): フレーム（=グリッド要素1枚分）の時刻

        Returns:
            (bytes, bool)
                - グリッド画像更新なし: (None, False)
                - グリッド画像更新あり＆未完成: (bytes, False)
                - グリッド画像更新あり＆完成: (bytes, True)

        Raises:
            ValueError: 入力フレームサイズ不正
        """
        # 入力フレームサイズチェック
        expected = self._in_w * self._in_h * 3
        if len(frame) != expected:
            raise ValueError(
                f"frame bytes size mismatch: got={len(frame)} expected={expected}"
            )

        # フレーム縮小
        img = np.frombuffer(frame, dtype=np.uint8).reshape((self._in_h, self._in_w, 3))
        tile_img = cv2.resize(
            img, (self._tile_w, self._tile_h), interpolation=cv2.INTER_AREA
        )
        cur_h = self._histogram(tile_img)

        # タイムスタンプオーバーレイ
        tile_for_grid = tile_img.copy()
        self._overlay_timestamp(tile_for_grid, ts)

        # 出力フレームタイムアウトチェック
        if self._grid_started_at is None:
            self._grid_started_at = ts
        if (
            self._tiles
            and (ts - self._grid_started_at).total_seconds() >= self._flush_timeout
        ):
            # グリッド画像完成
            grid_img = self._build_grid()
            grid_raw = grid_img.tobytes()

            # 内部状態をリセット
            # フレームを次グリッドの1枚目にする
            self._tiles.clear()
            self._tiles.append(tile_for_grid)
            self._prev_tile_hist = cur_h
            self._grid_started_at = ts

            return grid_raw, True

        # フレーム差分判定
        if self._prev_tile_hist is not None:
            d = cv2.compareHist(self._prev_tile_hist, cur_h, cv2.HISTCMP_BHATTACHARYYA)
            if d < self._diff_threshold:
                return None, False
        self._prev_tile_hist = cur_h

        # 出力タイル画像リスト追加
        self._tiles.append(tile_for_grid)

        # グリッド画像生成
        grid_img = self._build_grid()
        grid_raw = grid_img.tobytes()

        # 完成判定
        completed = len(self._tiles) >= self._grid_size
        if completed:
            self._tiles.clear()
            self._prev_tile_hist = None
            self._grid_started_at = None

        return grid_raw, completed

    def _build_grid(self) -> np.ndarray:
        """
        グリッド画像生成

        タイル配列から m x n のグリッド画像を合成する。

        配置規則:
            - 出力タイル画像リスト[0] を左上、右方向に埋め、右端で折り返して次の行へ進む。
            - 出力タイル画像リスト が途中でも、埋まっている分だけ配置する。
            - 未充填セルは黒で埋める。

        Returns:
            ndarray : 合成済みグリッド画像
        """
        grid_h = self._tile_h * self._rows
        grid_w = self._tile_w * self._cols
        grid = np.zeros((grid_h, grid_w, 3), dtype=np.uint8)

        for i, t in enumerate(self._tiles[: self._grid_size]):
            c = i % self._cols
            x0 = c * self._tile_w
            r = i // self._cols
            y0 = r * self._tile_h
            grid[y0 : y0 + self._tile_h, x0 : x0 + self._tile_w] = t

        return grid

    def _overlay_timestamp(self, img_bgr: np.ndarray, ts: datetime) -> None:
        """
        タイムスタンプオーバーレイ

        タイル画像の左上に時刻 "hh:mm:ss.SSS" を描画する。

        Args:
            img_bgr: 描画対象のタイル画像（BGR）
            ts: 描画する時刻（datetime）
        """
        ts_text = ts.strftime("%H:%M:%S.") + f"{ts.microsecond // 1000:03d}"

        cv2.putText(
            img_bgr,
            ts_text,
            TEXT_OFFSET,
            TEXT_FONT,
            TEXT_SCALE,
            TEXT_COLOR,
            TEXT_THICK,
            cv2.LINE_AA,
        )

    def _histogram(self, img: np.ndarray) -> np.ndarray:
        """
        ヒストグラム計算

        画像の色分布を粗く要約する。
        - BGR → HSV 変換
          - HSV: 照度変化や影に比較的強い
        - 特徴量計算
          - H（色相）× S（彩度）の 2次元ヒストグラム
        - 正規化
          - 画素数や明るさに依存しない比較をするため

        Args:
            img: 入力画像（BGR）

        Returns:
            特徴量ベクトル
        """
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
        h = cv2.calcHist([hsv], [0, 1], None, [32, 32], [0, 180, 0, 256])
        cv2.normalize(h, h, 0, 1, cv2.NORM_MINMAX)
        return h
