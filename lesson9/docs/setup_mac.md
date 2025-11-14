# Mac

## インストール
[SDK入門①〜社用車で走ったとこ全部見せます〜](../../lesson1/docs/setup_mac.md) +

### FFmpegインストール
```sh
brew install ffmpeg
ffmpeg -version
```

### 依存パッケージインストール
```sh
pip install numpy requests
```

### 利用

### サンプルプログラム
#### 音声+映像+字幕、多重化
```sh
python lesson9/src/download.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --meas_uuid <YOUR_MEAS_UUID> --gmap-api-key <YOUR_GMAP_API_KEY> --mux
```

#### 音声
```sh
python lesson9/src/download.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --meas_uuid <YOUR_MEAS_UUID> --tracks audio
```

#### 音声+映像、多重化
```sh
python lesson9/src/download.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --meas_uuid <YOUR_MEAS_UUID> --tracks audio video --mux
```

#### 開始〜終了時刻指定
```sh
python lesson9/src/download.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID> --start YYYY-MM-DDThh:mm:ss.SSSSSS+HH:MM --end YYYY-MM-DDThh:mm:ss.SSSSSS+HH:MM
```
または
```sh
python lesson9/src/download.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID> --start YYYY-MM-DDThh:mm:ss.SSSSSSZ --end YYYY-MM-DDThh:mm:ss.SSSSSSZ
```

#### FPS指定
```sh
python lesson9/src/download.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --meas_uuid <YOUR_MEAS_UUID> --outdir <YOUR_OUT_DIR>
```

#### FPS指定
```sh
python lesson9/src/download.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --meas_uuid <YOUR_MEAS_UUID> --tracks video  --fps 30 --mux
```
