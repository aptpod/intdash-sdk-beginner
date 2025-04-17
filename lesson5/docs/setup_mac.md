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
export PYTHONPATH=/path/to/your_workspace/intdash:
```

### サンプルプログラム
```sh
python lesson5/src/capture_screen.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID>  --dst_edge_uuid <YOUR_DST_EDGE_UUID>
```

### 可視化
[VM2M Stream Video V2](https://apps.apple.com/jp/app/vm2m-stream-video-v2/id1640464463)で再生します。

- Video
  - <YOUR_EDGE_UUID>
  - Data Type: `h264_frame`
  - Data Name: `1/h264`
