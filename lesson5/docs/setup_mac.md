# Mac

## インストール
[SDK入門①〜社用車で走ったとこ全部見せます〜](../../lesson1/docs/setup_mac.md) +<br>
[SDK入門③〜RTSPで映像配信するぞ〜](../../lesson3/docs/setup_mac.md) +<br>
[SDK入門④〜YOLOで物体検知しちゃう〜](../../lesson4/docs/setup_mac.md) +

### Pythonパッケージインストール
```sh
pip install mss
```

## 実行

### PYTHONPATH設定
```sh
echo $PYTHONPATH
export PYTHONPATH=/path/to/your_workspace
```

### サンプルプログラム
#### モニタ全体
```sh
python lesson5/src/capture_screen.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID>
```
#### モニタ番号指定
```sh
python lesson5/src/capture_screen.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID> --monitor <YOUR_MONITOR_NUMBER>
```

#### キャプチャ範囲オフセット指定
```sh
python lesson5/src/capture_screen.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID> --x <OFFSET_X> --y <OFFSET_Y>
```

#### キャプチャ範囲オフセット・幅・高さ指定
```sh
python lesson5/src/capture_screen.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID> --x <OFFSET_X> --y <OFFSET_Y> --w <WIDTH> --h <HEIGHT>
```

#### リサイズ幅・高さ指定
```sh
python lesson5/src/capture_screen.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID> --up_w <UPSTREAM_WIDTH> --up_h <UPSTREAM_HEIGHT>
```

### 可視化
[VM2M Stream Video V2](https://apps.apple.com/jp/app/vm2m-stream-video-v2/id1640464463)で再生します。

- Video
  - <YOUR_EDGE_UUID>
  - Data Type: `h264_frame`
  - Data Name: `1/h264`
