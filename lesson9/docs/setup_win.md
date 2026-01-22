# Windows 

## インストール
[SDK入門①〜社用車で走ったとこ全部見せます〜](../../lesson1/docs/setup_win.md) +

### FFmpegインストール
[FFmpeg公式サイト](https://ffmpeg.org/download.html)からWindows用のバイナリをダウンロードします。<br>
例: ffmpeg-release-full.7z

展開して任意のフォルダに配置します。<br>
例: C:¥ffmpeg-7.0.2

インストール先のパスを環境変数Pathに追加します。<br>
例: C:¥ffmpeg-7.0.2


```powershell
ffmpeg -version
```

### 依存パッケージインストール
```powershell
pip install numpy requests
```

## 実行

### PYTHONPATH設定
```powershell
echo $env:PYTHONPATH
$env:PYTHONPATH = "/path/to/your_workspace;"
```

### サンプルプログラム
#### 音声+映像+字幕、多重化
```powershell
python lesson9/src/download.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --meas_uuid <YOUR_MEAS_UUID> --gmap-api-key <YOUR_GMAP_API_KEY> --mux
```

#### 音声
```powershell
python lesson9/src/download.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --meas_uuid <YOUR_MEAS_UUID> --tracks audio
```

#### 音声+映像、多重化
```powershell
python lesson9/src/download.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --meas_uuid <YOUR_MEAS_UUID> --tracks audio video --mux
```

#### 音声(AAC)+映像、多重化
```powershell
python lesson9/src/download.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --meas_uuid <YOUR_MEAS_UUID> --tracks aac video --mux
```

#### 開始〜終了時刻指定
```powershell
python lesson9/src/download.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID> --start YYYY-MM-DDThh:mm:ss.SSSSSS+HH:MM --end YYYY-MM-DDThh:mm:ss.SSSSSS+HH:MM
```
または
```powershell
python lesson9/src/download.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID> --start YYYY-MM-DDThh:mm:ss.SSSSSSZ --end YYYY-MM-DDThh:mm:ss.SSSSSSZ
```

#### FPS指定
```powershell
python lesson9/src/download.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --meas_uuid <YOUR_MEAS_UUID> --outdir <YOUR_OUT_DIR>
```

#### FPS指定
```powershell
python lesson9/src/download.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --meas_uuid <YOUR_MEAS_UUID> --tracks video  --fps 30 --mux
```
