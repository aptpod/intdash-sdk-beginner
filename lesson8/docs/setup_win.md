# Windows 

## インストール
[SDK入門①〜社用車で走ったとこ全部見せます〜](../../lesson1/docs/setup_win.md) +<br>
[SDK入門②〜データ移行ツールの作り方〜](../../lesson2/docs/setup_win.md) +
[SDK入門④〜YOLOで物体検知しちゃう〜](../../lesson4/docs/setup_win.md)

## 実行

### PYTHONPATH設定
```sh
echo $PYTHONPATH
export PYTHONPATH=/path/to/your_workspace
```

### サンプルプログラム
#### データ名指定
```sh
python lesson8/src/upload.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID> --src_path <YOUR_MP4FILE> --data_name <YOUR_DATA_NAME>
```

#### 基準時刻指定
```sh
python lesson8/src/upload.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID> --src_path <YOUR_MP4FILE> --basetime <YOUR_BASETIME>
```

### 可視化
Data Visualizerに[Datファイル](../dat/Video.dat)をインポート
- Video
  - <YOUR_EDGE_UUID>
  - Data Type: `h264_frame`
  - Data Name: `video/h264`
