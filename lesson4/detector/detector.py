from typing import Tuple

import cv2
import numpy as np


class Detector:
    """
    物体検出

    Attributes:
        net (Net): 検出モデル
        class_names (list(str)): 物体クラス名リスト
        output_layers (list(str)): 出力レイヤー名リスト
        target_size (tulple[int, int]): 検出後フレームサイズ
    """

    def __init__(
        self,
        weight_file: str,
        config_file: str,
        name_file: str,
        target_size: Tuple[int, int],
    ) -> None:
        """
        コンストラクタ

        Args:
            weight_file (str): 重みファイルパス
            config_file (str): 設定ファイルパス
            name_file (str): クラス名ファイルパス
            target_size (tuple): 変換後サイズ(width, height)
        """
        self.net = cv2.dnn.readNet(weight_file, config_file)
        with open(name_file, "r") as f:
            self.class_names = [line.strip() for line in f.readlines()]
        layer_names = self.net.getLayerNames()
        self.output_layers = [
            layer_names[i - 1] for i in self.net.getUnconnectedOutLayers()
        ]
        self.target_size = target_size

    def detect(self, frame: bytes) -> Tuple[bytes, int]:
        """
        物体検出

        準備
        - RAWデータをBGRデータにリシェイプ
        - モデルにデータ読み込み
        物体検出
        - YOLO推論実行
        - 検出オブジェクト（矩形、精度、クラス名）抽出
        - 重複を非最大抑制で削除
        戻り値生成
        - 矩形描画・人数カウント

        Args:
            frame (bytes): 元フレーム

        Returns:
            tuple(bytes, int): 矩形描画後フレーム, 検出人数
        """

        # 準備
        frame_reshaped = (
            np.frombuffer(frame, np.uint8).reshape(
                (self.target_size[1], self.target_size[0], 3)
            )
        ).copy()
        blob = cv2.dnn.blobFromImage(
            frame_reshaped, 1 / 255.0, self.target_size, swapRB=True, crop=False
        )
        self.net.setInput(blob)

        # 物体検出
        outs = self.net.forward(self.output_layers)

        height, width, _ = frame_reshaped.shape
        boxes = []
        confidences = []
        class_ids = []
        for out in outs:
            for detection in out:
                scores = detection[5:]
                class_id = np.argmax(scores)
                confidence = scores[class_id]
                if confidence > 0.2:  # 信頼度0.2以上で全ての物体を検出
                    center_x = int(detection[0] * width)
                    center_y = int(detection[1] * height)
                    w = int(detection[2] * width)
                    h = int(detection[3] * height)
                    x = int(center_x - w / 2)
                    y = int(center_y - h / 2)
                    boxes.append([x, y, w, h])
                    confidences.append(float(confidence))
                    class_ids.append(class_id)

        indices = cv2.dnn.NMSBoxes(boxes, confidences, 0.2, 0.4)

        # 矩形描画・人数カウント
        count = 0
        for i in indices:
            x, y, w, h = boxes[i]

            if self.class_names[class_ids[i]] == "person":
                color = (0, 255, 0)
                count = count + 1
            else:
                color = (0, 0, 255)
            label = f"{self.class_names[class_ids[i]]}: {confidences[i]:.2f}"

            cv2.rectangle(frame_reshaped, (x, y), (x + w, y + h), color, 2)
            cv2.putText(
                frame_reshaped,
                label,
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2,
            )

        return frame_reshaped.tobytes(), count
