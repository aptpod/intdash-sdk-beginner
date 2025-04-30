# Mac

## インストール

[SDK入門①〜社用車で走ったとこ全部見せます〜](../../lesson1/docs/setup_mac.md) +

### Buf CLIインストール

```sh
brew install bufbuild/buf/buf
buf --version
```
### Protocol Buffersエンコーダーの生成

#### プロトコル定義ファイルのダウンロード
[intdash API specificationページ](https://docs.intdash.jp/api/intdash-api/v2.7.0/spec_public.html#tag/MeasurementService_Measurement-Sequences/operation/createProjectMeasurementSequenceChunks)から[プロトコル定義ファイルページ](https://docs.intdash.jp/api/measurement/v1.18/proto/index.html)に遷移し、プロトコル定義ファイル `protocol.proto` をダウンロードします。


#### プロトコル定義ファイル配置
```sh
mkdir -p proto/intdash/v1/ 
cp path/to/protocol.proto proto/intdash/v1/  
sed -i -e "s/package pb;/package intdash.v1;/g" proto/intdash/v1/protocol.proto
```

#### Buf CLI定義ファイル作成
```sh
cat << EOS > ./proto/buf.yaml
version: v1
breaking:
  use:
    - FILE
lint:
  use:
    - DEFAULT
EOS

cat << EOS > ./buf.gen.yaml
version: v1
managed:
  enabled: true
plugins:
  - plugin: buf.build/protocolbuffers/python:v23.4
    out: gen
EOS

buf generate proto
ls -l gen
```
### protobufパッケージインストール
```sh
pip install protobuf
```

### メモリ使用量表示
```sh
pip install psutil
```

## 実行
### PYTHONPATH設定
```sh
echo $PYTHONPATH
export PYTHONPATH=/path/to/your_workspace
```

### データ移行ツール
#### エクスポート
```sh
python lesson2/migrate/src/meas_export.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --meas_uuid <YOUR_MEAS_UUID>
```

#### エクスポート メモリ消費量低減：随時取得版
```sh
python lesson2/migrate/src/meas_export_mem.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --meas_uuid <YOUR_MEAS_UUID>
```

#### インポート
```sh
python lesson2/migrate/src/meas_import.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID> --src_file <EXPORTED_JSON_FILE>
```

#### インポート メモリ消費量低減：随時読み出し版
```sh
python lesson2/migrate/src/meas_import_mem.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID> --src_file <EXPORTED_JSON_FILE>
```

### GPS距離算出
```sh
python lesson2/distance/src/distance.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --meas_uuid <YOUR_MEAS_UUID>
```

### 可視化
- GPS距離算出
Data Visualizerに[Datファイル](../distance/dat/Distance.dat)をインポート
