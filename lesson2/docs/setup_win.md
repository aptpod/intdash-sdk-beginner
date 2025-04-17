# Windows

## インストール

[SDK入門①〜社用車で走ったとこ全部見せます〜](../../lesson1/docs/setup_win.md) +

### Buf CLIインストール

[Buf公式サイト](https://buf.build/docs/installation/)の「Downloads」セクションからWindows用のバイナリをダウンロードします。<br>
例: buf-Windows-x86_64.exe

buf.exeにリネームして任意のフォルダに配置します。<br>
例: C:¥buf

インストール先のパスを環境変数Pathに追加します。<br>
例: C:¥buf

```powershell
buf --version
```
### Protocol Buffersエンコーダーの生成

#### プロトコル定義ファイルのダウンロード
[intdash API specificationページ](https://docs.intdash.jp/api/intdash-api/v2.7.0/spec_public.html#tag/MeasurementService_Measurement-Sequences/operation/createProjectMeasurementSequenceChunks)から[プロトコル定義ファイルページ](https://docs.intdash.jp/api/measurement/v1.18/proto/index.html)に遷移し、プロトコル定義ファイル `protocol.proto` をダウンロードします。


#### プロトコル定義ファイル配置
```powershell
mkdir proto\intdash\v1
copy path\to\protocol.proto proto\intdash\v1\
(Get-Content proto\intdash\v1\protocol.proto -Encoding UTF8) -replace '^package pb;', 'package intdash.v1;' | Set-Content -Encoding UTF8 proto\intdash\v1\protocol.proto
```

#### Buf CLI定義ファイル作成
```powershell
@"
version: v1
breaking:
use:
- FILE
use:
- DEFAULT
"@ > ./proto/buf.yaml

@"
version: v1
managed:
enabled: true
plugins:
- plugin: buf.build/protocolbuffers/python:v23.4
out: gen
"@ > ./buf.gen.yaml

buf generate proto
dir gen
```
### protobufパッケージインストール
```powershell
pip install protobuf
```
### メモリ使用量表示
```powershell
pip install psutil
```

## 実行
### PYTHONPATH設定
```powershell
echo $env:PYTHONPATH
$env:PYTHONPATH = "/path/to/your_workspace;"
```

### データ移行ツール
#### エクスポート
```powershell
python lesson2/migrate/src/meas_export.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --meas_uuid <YOUR_MEAS_UUID>
```
#### エクスポート メモリ消費量低減：随時取得版
```powershell
python lesson2/migrate/src/meas_export_mem.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --meas_uuid <YOUR_MEAS_UUID>
```

#### インポート
```powershell
python lesson2/migrate/src/meas_import.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID> --src_file <EXPORTED_JSON_FILE>
```

#### インポート メモリ消費量低減：随時読み出し版
```powershell
python lesson2/migrate/src/meas_import_mem.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID> --src_file <EXPORTED_JSON_FILE>
```

### GPS距離算出
```powershell
python lesson2/distance/src/distance.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --meas_uuid <YOUR_MEAS_UUID>
```

### 可視化
- GPS距離算出
Data Visualizerに[Datファイル](../distance/dat/Distance.dat)をインポート
