# Windows 

## ローカルPCインストール
### Python依存パッケージインストール
```powershell
pip install boto3 requests pytest
```

## AWS構築
### カスタムLambdaレイヤー作成
#### 依存パッケージインストール
```powershell
mkdir -p path\to\workdir\python\lib\python3.12\site-packages
pip3.12 install pydantic python-dateutil urllib3 -t path\to\workdir\python\lib\python3.12\site-packages
pip3.12 install protobuf -t path\to\workdir\python\lib\python3.12\site-packages
```

#### ZIPファイル作成
```powershell
Copy-Item -Path intdash, gen -Destination path\to\workdir\python\lib\python3.12\site-packages\ -Recurse
cd path\to\workdir
Get-ChildItem -Path . -Recurse -Filter "*.pyc" | Remove-Item -Force
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Compress-Archive -Path python -DestinationPath intdash_sdk.zip
```

### カスタムLambdaレイヤー作成（Dockerコンテナ利用）
ローカルPCでDockerが起動しているなら、DockerfileでZIPファイルを生成できます。

#### 準備
- protocol.protoを実行ディレクトリに保存

#### ビルド
```powershell
docker build -t lambda-layer -f lesson6/intdash-distance/docker/Dockerfile .
```

#### 実行
```powershell
docker run --name lambda-layer lambda-layer
```

#### ZIP取得
```powershell
docker cp lambda-layer:/intdash_sdk.zip ./intdash_sdk.zip
```

### Lambda関数作成

#### ZIPファイル作成
```powershell
cd lesson6/intdash-distance/src
Get-ChildItem -Path . -Recurse -Filter "*.pyc" | Remove-Item -Force
Get-ChildItem -Path . -Recurse -Directory -Filter "__pycache__" | Remove-Item -Recurse -Force
Compress-Archive -Path ./* -DestinationPath ..\deployment_package.zip
```
#### ZIPファイルアップロード
Lambdaコード画面から、作成したZIPファイルをアップロードします。

#### タイムアウト設定
タイムアウト：5分

#### 環境変数設定
- `API_TOKEN`: サーバー環境にアクセスするAPIトークン
- `API_URL`: サーバー環境のURL
- `FETCH_SIZE`: データポイントを何件ずつ処理するか
- `ORIGIN_LAT`: 基準点（緯度）
- `ORIGIN_LON`: 基準点（経度）
- `SLACK_URL`: 通知先Slack

#### Lambdaレイヤー追加
- intdash SDK: 作成したカスタムLambdaレイヤー
- `requests`: 公開ARNを指定

### レスポンス返却Lambda作成
Lambdaコード画面に`lesson6/invoke-distance/src/lambda_function.py`の内容を貼り付けます。

#### 環境変数設定
- `SECRET_KEY`: Webhook設定に登録する任意の文字列

### API Gateway作成
POSTリクエストを受けるAPI Gatewayを作成します。

レスポンス返却Lambdaと統合します。

## 実行

### PYTHONPATH設定
```powershell
echo $env:PYTHONPATH
$env:PYTHONPATH = "/path/to/your_workspace;"
```

### Webhook設定ツール
#### `list`: 一覧
プロジェクトに属するWebhook設定を一覧表示します。
```powershell
python lesson6/cli/src/hook_cli.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> list
```

#### `export`: 取得・JSON保存
1つのWebhook設定を表示します。

`--dest_dir`を指定するとJSONファイルに設定を保存します。

```powershell
python lesson6/cli/src/hook_cli.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> export --hook_uuid <YOUR_HOOK_UUID> --dest_dir <YOUR_DEST_DIR>
```

#### `import`: 登録
指定したJSONファイルを元にWebhook設定を登録します。

`hook_uuid`を指定すると既存のWebhook設定を更新します。

```powershell
python lesson6/cli/src/hook_cli.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> import --src_path=<YOUR_SRC_PATH> --hook_uuid <YOUR_HOOK_UUID>
```

テンプレートとして`lesson6/cli/config/hook.json`を用意しています。

#### `delete`: 削除
既存のWebhook設定を削除します。

```powershell
python lesson6/cli/src/hook_cli.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> delete --hook_uuid <YOUR_HOOK_UUID>
```

#### `test`: テスト
既存のWebhook設定をテストします。

実際に登録されている通知先URLにWebhookリクエストを送信します。

```powershell
python lesson6/cli/src/hook_cli.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> test --hook_uuid <YOUR_HOOK_UUID> --resource_type measurement --action created
```
`npm`の`openapi-generator-cli`だと`created`/`updated`/`deleted`以外の`action`がエラーになるようです。その場合は、curlコマンドで直接Test Hook APIを叩いて確認します。

```powershell
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

```powershell
pytest -v -p no:warnings lesson6/intdash-distance/test/test_lambda_function.py 
```

##### レスポンス返却プログラム

テストコード`lesson6/intdash-distance/test/test_lambda_function.py`を修正します。

- 環境変数
  - `SECRET_KEY`

テストコードを起動します。

```powershell
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

### 可視化
Data Visualizerに[Datファイル](../intdash-distance/dat/Distance.dat)をインポート

Slack通知のData Visualizerのリンクをクリック