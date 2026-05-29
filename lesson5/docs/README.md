# SDK入門⑤〜iPadでData Visualizerを見る会〜

PCの画面キャプチャしてアップストリームします。

![アーキテクチャ](../images/arch.png)

![Stream Video](../images/ipad.png)

## 依存関係
- REST API用intdash SDK for Python>=v2.7.0
- pydantic>=2.13.4
- python-dateutil>=2.9.0.post0
- urllib3>=2.7.0
- iscp>=1.0.0
- opencv-python>=4.13.0.92
- numpy>=2.4.6
- PyGObject>=3.56.2
- mss>=10.2.0

## インストール&実行

- [Mac](./setup_mac.md)

- [Windows](./setup_win.md)

## 詳細
- [SDK入門⑤〜iPadでData Visualizerを見る会〜](https://tech.aptpod.co.jp/entry/2024/12/20/100000) 

## 制限
- キャプチャ範囲オフセット・幅・高さ、リサイズ幅・高さはエンコードのために数ピクセル丸め
