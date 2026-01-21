# Mac

## インストール
[SDK入門④〜YOLOで物体検知しちゃう〜](./lesson4/docs/README.md) +

### OpenAIパッケージインストール
```sh
pip install openai
```

## 実行

### PYTHONPATH設定
```sh
echo $PYTHONPATH
export PYTHONPATH=/path/to/your_workspace
```

### サンプルプログラム
#### 同一エッジ指定
```sh
python lesson10/src/detect_people.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID> --openai_key <OPENAI_KEY>
```

#### 別エッジ指定
```sh
python lesson10/src/detect_people.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID> --openai_key <OPENAI_KEY> --dst_edge_uuid <YOUR_DST_EDGE_UUID>
```
#### プロンプトファイル指定
```sh
python lesson10/src/detect_people.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID> --openai_key <OPENAI_KEY> --prompt_path <YOUR_PROMPT_PATH>
```

### 収集開始
[intdash Motion V2](https://apps.apple.com/in/app/intdash-motion-v2/id1632857226)でデータ収集を開始します。

- <YOUR_EDGE_UUID>
- Video
    - Data Type: `h264_frame`
    - Data Name: `1/h264`

### 可視化
Data Visualizerに[Datファイル](../dat/Summarize%20Service.dat)をインポート
- <YOUR_EDGE_UUID>
- プレビュー画像
  - Data Type: `jpeg`
  - Data Name: `11/preview`
- 要約画像
  - Data Type: `jpeg`
  - Data Name: `12/summary`
- 要約結果
  - Data Type: `string`
  - Data Name: `12/answer`
