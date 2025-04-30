# Mac

## インストール
[SDK入門①〜社用車で走ったとこ全部見せます〜](../../lesson1/docs/setup_mac.md) +<br>
[SDK入門③〜RTSPで映像配信するぞ〜](../../lesson3/docs/setup_mac.md) +

### Gstreamerインストール
```sh
brew install gstreamer
gst-launch-1.0 --version
gst-launch-1.0 videotestsrc ! autovideosink
```
### Pythonパッケージインストール
```sh
pip install opencv-python numpy PyGObject
```

## 実行

### PYTHONPATH設定
```sh
echo $PYTHONPATH
export PYTHONPATH=/path/to/your_workspace
```

### サンプルプログラム
```sh
python lesson4/src/detect_people.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID> --dst_edge_uuid <YOUR_DST_EDGE_UUID>
```

### 収集開始
[intdash Motion V2](https://apps.apple.com/in/app/intdash-motion-v2/id1632857226)でデータ収集を開始します。

- Video
  - <YOUR_EDGE_UUID>
  - Data Type: `h264_frame`
  - Data Name: `1/h264`


### 可視化
Data Visualizerに[Datファイル](../dat/Detect%20People.dat)をインポート
- Video
  - <YOUR_EDGE_UUID>
  - Data Type: `h264_frame`
  - Data Name: `10/h264`
