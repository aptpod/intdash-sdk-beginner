# Windows

## インストール

### クライアントライブラリインストール

```powershell
pip install iscp
```

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

### MediaMTXインストール
[MediaMTX](https://github.com/bluenviron/mediamtx?tab=readme-ov-file#installation)のバイナリ（.tar.gz）をダウンロードして展開します。
例: mediamtx_v1.9.3_windows_amd64.zip

設定ファイル`mediamtx.yml`を編集して、送信するデータに合わせてFPS設定を変えておきます。

```powershell
  rpiCameraFPS: 15
```

## 実行

### MediaMTX
```powershell
cd /path/to/yml_directory
mediamtx
```

### PYTHONPATH設定
```powershell
echo $env:PYTHONPATH
$env:PYTHONPATH = "/path/to/your_workspace;"
```

### サンプルプログラム
```powershell
python lesson3/src/rtsp_stream.py  --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID>
```

### 収集開始
[intdash Motion V2](https://apps.apple.com/in/app/intdash-motion-v2/id1632857226)でデータ収集を開始します。

- Data Type: `h264_frame`
- Data Name: `1/h264`

### ffplay
```powershell
ffplay -window_title "After RTSP" rtsp://localhost:8554/stream
```
