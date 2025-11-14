# Windows

## インストール

### Javaインストール

[Java公式サイト](https://www.oracle.com/java/technologies/javase-downloads.html)からインストーラーをダウンロードします。<br>
例: jdk-23_windows-x64_bin.exe

インストール先のパスを環境変数Pathに追加します。<br>
例: C:\Program Files\Java\jdk-23\bin

```powershell
java --version
```

### npmインストール
[Node.js公式サイト](https://nodejs.org/en)からLTSインストーラーをダウンロードします。<br>
例: node-v22.11.0-x64.msi

インストール先のパスが環境変数Pathに自動で追加されます。<br>
例: C:\Users\<username>\AppData\Roaming\npm

```powershell
npm -v
```

PowerShellの実行ポリシーがRestrictedの場合はで変更します。
```powershell
Get-ExecutionPolicy
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

### OpenAPI Generatorインストール
```powershell
npm install @openapitools/openapi-generator-cli
npx @openapitools/openapi-generator-cli version
```

### intdash SDK for Python生成
```powershell
$env:VERSION = "v2.7.0"
$env:SRC_DIR = "."
npx @openapitools/openapi-generator-cli version-manager set 6.1.0
npx @openapitools/openapi-generator-cli generate `
-g python `
-i https://docs.intdash.jp/api/intdash-api/$env:VERSION/openapi_public.yaml `
--package-name=intdash `
--additional-properties=generateSourceCodeOnly=true `
--global-property "modelTests=false" `
--global-property "apiTests=false" `
--global-property "modelDocs=true" `
--global-property "apiDocs=true" `
--http-user-agent=SDK-Sample-Python-Client/Gen-By-OASGenerator `
-o $env:SRC_DIR
dir intdash
```

### Pythonインストール
[Python公式サイト](https://www.python.org/downloads/)からインストーラーをダウンロードします。<br>
例: python-3.12.7-amd64.exe

インストール先のパスを環境変数Pathに追加します。<br>
例: C:\Users\<username>\AppData\Local\Programs\Python\Python312

```powershell
python --version
```

### Python仮想環境作成
```powershell
python -m venv venv
venv\Scripts\activate
python --version
pip --version
```
### 依存パッケージインストール
```powershell
pip install pydantic python-dateutil urllib3
```

### 利用パッケージインストール
```powershell
pip install folium matplotlib
```

## 実行
### PYTHONPATH設定
```powershell
echo $env:PYTHONPATH
$env:PYTHONPATH = "/path/to/your_workspace;"
```

### サンプルプログラム実行
```powershell
python lesson1/src/gnss_plot.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuids <YOUR_EDGE_UUID1> <YOUR_EDGE_UUID2> <YOUR_EDGE_UUID3>
```
