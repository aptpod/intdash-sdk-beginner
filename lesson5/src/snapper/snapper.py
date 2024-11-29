from typing import Tuple

import cv2
import mss
import numpy as np


class Snapper:
    """
    画面キャプチャ

    キャプチャ結果を返す

    Attributes:
        sct (MSSBase): MSSインスタンス
        monitor (Monitor): モニタインスタンス
        targer_size (tuple(int, int)): 出力サイズ
    """

    def __init__(self, target_size: Tuple[int, int], monitors_number: int = 1) -> None:
        """
        コンストラクタ

        Params:
            targer_size (tuple(int, int)): 出力サイズ
            monitors_number (int): モニタ番号（デフォルト：プライマリモニタ）
        """
        self.sct = mss.mss()
        self.monitor = self.sct.monitors[monitors_number]
        self.target_size = target_size

    def get(self) -> bytes:
        """
        キャプチャRAWフレーム取得

        Returns:
            (bytes): RAWフレーム（BGR）
        """
        img = self.sct.grab(self.monitor)
        frame = np.asarray(img)[:, :, :3]  # BGRAからBGRに変換
        frame = cv2.resize(frame, self.target_size)
        return frame.tobytes()
