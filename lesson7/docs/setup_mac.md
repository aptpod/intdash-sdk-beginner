# Mac

## インストール

[SDK入門①〜社用車で走ったとこ全部見せます〜](../../lesson1/docs/setup_mac.md) +<br>
[SDK入門③〜RTSPで映像配信するぞ〜](../../lesson3/docs/setup_mac.md)

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

### リプレイ
#### 計測指定
```sh
python lesson7/src/replay.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --meas_uuid <YOUR_MEAS_UUID> 
```
#### 開始〜終了時刻指定
```sh
python lesson7/src/replay.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID> --start YYYY-MM-DDThh:mm:ss.SSSSSS+HH:MM --end YYYY-MM-DDThh:mm:ss.SSSSSS+HH:MM
```
または
```sh
python lesson7/src/replay.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --edge_uuid <YOUR_EDGE_UUID> --start YYYY-MM-DDThh:mm:ss.SSSSSSZ --end YYYY-MM-DDThh:mm:ss.SSSSSSZ
```

#### データフィルター指定
```sh
python lesson7/src/replay.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --meas_uuid <YOUR_MEAS_UUID> --data_id_filter <DATA_TYPE>:<DATA_NAME>,<DATA_TYPE>:<DATA_NAME>
```

#### 倍速指定
```sh
python lesson7/src/replay.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --meas_uuid <YOUR_MEAS_UUID> --speed <SPEED>
```

#### 別環境指定
```sh
python lesson7/src/replay.py --api_url https://example.intdash.jp --api_token <YOUR_API_TOKEN> --project_uuid <YOUR_PROJECT_UUID> --meas_uuid <YOUR_MEAS_UUID> --dst_api_url https://example.intdash.jp --dst_api_token <YOUR_API_TOKEN> --dst_project_uuid <YOUR_PROJECT_UUID> --dst_edge_uuid <YOUR_EDGE_UUID>
```

### 可視化
計測データに依存
- Terminal System 2 のGNSS(UBX)の場合
  - Data VisualizerにDatファイル(ubx.dat)をインポート
