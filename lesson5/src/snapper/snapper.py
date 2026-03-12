import logging
from typing import Optional, Tuple

import cv2
import mss
import numpy as np


class Snapper:
    """
    画面キャプチャ

    キャプチャ結果を返す

    Attributes:
        sct (MSSBase): MSSインスタンス
        capture_area (dict): キャプチャ範囲
        resized_size (tuple(int, int)): リサイズサイズ
    """

    ALIGNMENT = 4  # ピクセル丸めサイズ（H264 / I420 alignmentのため）

    @staticmethod
    def _align(value: int) -> int:
        """
        ピクセル丸め
        """
        return value - (value % Snapper.ALIGNMENT)

    def __init__(
        self,
        monitors_number: int = 1,
        offset: Tuple[int, int] = (0, 0),
        capture_size: Optional[Tuple[int, int]] = None,
        resized_size: Optional[Tuple[int, int]] = None,
    ) -> None:
        """
        コンストラクタ

        - キャプチャ範囲がモニタをはみ出る・指定がない場合はモニタサイズを採用
        - リサイズ幅・高さ指定がない場合はキャプチャ範囲幅・高さを採用
        - キャプチャ幅・高さ、リサイズ幅・高さを丸める


        Params:
            monitors_number (int): モニタ番号（デフォルト：プライマリモニタ）
            offset (tuple(int, int)): キャプチャ範囲オフセット（デフォルト：モニタ左上）
            capture_size (tuple(int, int)): キャプチャ範囲サイズ（デフォルト：モニタサイズ）
            resized_size (tuple(int, int)): キャプチャ範囲サイズ（デフォルト：モニタサイズ）
        """
        self.sct = mss.mss()
        monitor = self.sct.monitors[monitors_number]
        x, y = offset

        # キャプチャ範囲がモニタをはみ出る・指定がない場合はモニタサイズを採用
        if capture_size is not None:
            w, h = capture_size
            if w > monitor["width"] - x or h > monitor["height"] - y:
                w, h = monitor["width"] - x, monitor["height"] - y
        else:
            w, h = monitor["width"] - x, monitor["height"] - y

        # リサイズ幅・高さ指定がない場合はキャプチャ範囲幅・高さを採用
        if resized_size is not None:
            resized_w, resized_h = resized_size
        else:
            resized_w, resized_h = w, h

        # キャプチャ幅・高さ、リサイズ幅・高さを丸める
        w, h = self._align(w), self._align(h)
        resized_w = self._align(resized_w)
        resized_h = self._align(resized_h)
        self.resized_size = resized_w, resized_h

        self.capture_area = {
            "left": monitor["left"] + x,
            "top": monitor["top"] + y,
            "width": w,
            "height": h,
        }
        logging.info(
            f"capture_area: {self.capture_area} resized_size: {self.resized_size}"
        )

    def get(self) -> bytes:
        """
        キャプチャRAWフレーム取得

        Returns:
            (bytes): RAWフレーム（BGR）
        """
        img = self.sct.grab(self.capture_area)
        frame = np.asarray(img)[:, :, :3]  # BGRAからBGRに変換
        frame = cv2.resize(frame, self.resized_size)
        return frame.tobytes()

    def get_resized_size(self) -> Tuple[int, int]:
        """
        リサイズ幅・高さ
        """
        return self.resized_size
