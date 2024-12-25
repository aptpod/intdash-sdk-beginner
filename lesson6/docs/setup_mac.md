# Mac

## ローカルPCインストール
### Python依存パッケージインストール
```sh
pip install boto3 requests pytest
```

## AWS構築
### カスタムLambdaレイヤー作成（手動）
#### 依存パッケージインストール

```sh
mkdir -p path/to/workdir
cd path/to/workdir
python -m venv venv
. ./venv/bin/activate
pip install pydantic python-dateutil urllib3
pip install protobuf
```

#### ZIPファイル作成
```sh
mkdir -p python/lib/python3.12/site-packages
cd path/to//intdash-sdk-workspace
cp -r intdash gen path/to/workdir/venv/lib/python3.12/site-packages/* path/to/python/lib/python3.12/site-packages
cd path/to/workdir
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -r {} +
zip -r intdash_sdk.zip python
```

### カスタムLambdaレイヤー作成（Dockerコンテナ利用）
#### 準備
- protocol.protoを実行ディレクトリに保存

#### ビルド
```sh
docker build -t lambda-layer -f lesson6/intdash-distance/docker/Dockerfile .
```

#### 実行
```sh
docker run --name lambda-layer lambda-layer
```

#### ZIP取得
```sh
docker cp lambda-layer:/intdash_sdk.zip ./intdash_sdk.zip
```

### Lambda関数作成

#### ZIPファイル作成
```sh
cd lesson6/intdash-distance/src
find . -name "*.pyc" -delete
find . -name "__pycache__" -type d -exec rm -r {} +
zip -r ../deployment_package.zip .
```

## 実行

### PYTHONPATH設定
```sh
echo $PYTHONPATH
export PYTHONPATH=/path/to/your_workspace/intdash:
```

### Webhook設定ツール
#### `list`: 一覧
プロジェクトに属するWebhook設定を一覧表示します。
```sh
python lesson6/cli/src/hook_cli.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> list
```

#### `export`: 取得・JSON保存
1つのWebhook設定を表示します。

`--dest_dir`を指定するとJSONファイルに設定を保存します。

```sh
python lesson6/cli/src/hook_cli.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> export --hook_uuid <YOUR_HOOK_UUID> --dest_dir <YOUR_DEST_DIR>
```

#### `import`: 登録
指定したJSONファイルを元にWebhook設定を登録します。

`hook_uuid`を指定すると既存のWebhook設定を更新します。

```sh
python lesson6/cli/src/hook_cli.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> import --src_path=<YOUR_SRC_PATH> --hook_uuid <YOUR_HOOK_UUID>
```

テンプレートとして`lesson6/cli/config/hook.json`を用意しています。

#### `delete`: 削除
既存のWebhook設定を削除します。

```sh
python lesson6/cli/src/hook_cli.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> delete --hook_uuid <YOUR_HOOK_UUID>
```

#### `test`: テスト
既存のWebhook設定をテストします。

実際に登録されている通知先URLにWebhookリクエストを送信します。

```sh
python lesson6/cli/src/hook_cli.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> test --hook_uuid <YOUR_HOOK_UUID> --resource_type measurement --action created
```
`npm`の`openapi-generator-cli`だと`created`/`updated`/`deleted`以外の`action`がエラーになるようです。その場合は、curlコマンドで直接Test Hook APIを叩いて確認します。

```sh
export API_TOKEN=<YOUR_API_TOKEN>
curl -i -X PATCH https://example.intdash.jp/api/v1/webhook/hooks/<YOUR_HOOK_UUID>/test \
-H "X-Intdash-Token: ${API_TOKEN}" \
-d '{
  "resource_type": "measurement",
  "action": "completed"
}'
```

### 距離算出
#### テストコード実行
##### 距離算出プログラム
テストコード`lesson6/intdash-distance/test/test_lambda_function.py`を修正します。

- 環境変数
  - `API_URL`
  - `API_TOKEN`
- イベント情報`event`
  - `project_uuid`
  - `measurement_uuid`
    - GPSデータを含む計測を設定します。

テストコードを起動します。

```sh
pytest -v -p no:warnings lesson6/intdash-distance/test/test_lambda_function.py 
```

##### レスポンス返却プログラム

テストコード`lesson6/intdash-distance/test/test_lambda_function.py`を修正します。

- 環境変数
  - `SECRET_KEY`

テストコードを起動します。

```sh
pytest -v -p no:warnings lesson6/intdash-distance/test/test_lambda_function.py
```

#### 計測
##### 計測開始
[intdash Motion V2](https://apps.apple.com/in/app/intdash-motion-v2/id1632857226)でデータ収集を開始します。

- Video
  - <YOUR_EDGE_UUID>
  - Data Type: `h264_frame`
  - Data Name: `1/h264`

##### 計測完了
Motionのデータ収集を停止します。

Slack通知されるData Visualizerのリンクをクリックします。

### 可視化
Data Visualizerに[Datファイル](../intdash-distance/dat/Distance.dat)をインポート
