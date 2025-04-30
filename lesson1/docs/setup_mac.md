# Mac

## インストール

### Javaインストール

```sh
brew install openjdk
java --version
```

### npmインストール
```sh
brew install node
npm -v
```

### OpenAPI Generatorインストール
```sh
npm install @openapitools/openapi-generator-cli
npx @openapitools/openapi-generator-cli version  
```

### intdash SDK for Python生成
```sh
VERSION=v2.7.0
SRC_DIR="."
./node_modules/.bin/openapi-generator-cli version-manager set 6.1.0
./node_modules/.bin/openapi-generator-cli generate \
-g python -i https://docs.intdash.jp/api/intdash-api/${VERSION}/openapi_public.yaml \
    --package-name=intdash \
    --additional-properties=generateSourceCodeOnly=true \
    --global-property=modelTests=false,apiTests=false,modelDocs=true,apiDocs=true \
    --http-user-agent=SDK-Sample-Python-Client/Gen-By-OASGenerator \
    -o "$SRC_DIR"
ls -l intdash
```

### Pythonインストール

```sh
brew install python
python --version
```
### Python仮想環境作成
```sh
python3.xx -m venv venv
. ./venv/bin/activate
python --version
pip --version
```
### 依存パッケージインストール
```sh
pip install pydantic python-dateutil urllib3
```

### 利用パッケージインストール
```sh
pip install folium matplotlib
```

## 実行
### PYTHONPATH設定
```sh
echo $PYTHONPATH
export PYTHONPATH=/path/to/your_workspace
```

### サンプルプログラム実行
```sh
python lesson1/src/gnss_plot.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuids <YOUR_EDGE_UUID1> <YOUR_EDGE_UUID2> <YOUR_EDGE_UUID3>
```
