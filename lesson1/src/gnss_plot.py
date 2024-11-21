import argparse
import base64
import json
import logging
import struct
import sys
import time
import traceback
from math import atan2, cos, radians, sin, sqrt

import folium
import matplotlib.colors as mcolors
import matplotlib.pyplot as plt

from intdash import ApiClient, Configuration
from intdash.api import (
    measurement_service_data_points_api,
    measurement_service_measurements_api,
)

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# 定数
ORIGIN = (35.6878973, 139.717092)  # 会社
MAP_ZOOM_START = 8
CIRCLE_RADIUS = 3
CIRCLE_OPACITY = 0.8
SAMPLE_INTERVAL = 600  # 1/1sec > 1/10min
CMAP = plt.get_cmap("jet")
NORM = mcolors.Normalize(vmin=0, vmax=250)
LIMIT = 10


def get_client(api_url: str, api_token: str) -> ApiClient:
    """
    APIクライアント取得

    Args:
        api_url: APIのURL
        api_token: APIトークン

    Returns:
        ApiClient: APIクライアント
    """
    configuration = Configuration(
        host=f"{api_url}/api", api_key={"IntdashToken": api_token}
    )
    client = ApiClient(configuration)
    return client


def get_meas_list(client: ApiClient, project_uuid: str, edge_uuid: str) -> list:
    """
    エッジ計測リスト取得

    Args:
        client: APIクライアント
        project_uuid: プロジェクトUUID
        edge_uuid: エッジUUID

    Returns:
        list: 計測リスト
    """

    api = measurement_service_measurements_api.MeasurementServiceMeasurementsApi(client)
    measurements = api.list_project_measurements(
        project_uuid=project_uuid, edge_uuid=edge_uuid, limit=LIMIT
    )
    return measurements["items"]


def parse_gnrmc(gnrmc: str) -> tuple:
    """
    GNRMCパース

    緯度（ddmm.mmmm）・N/S・経度（ddmm.mmmm）・E/Wを抽出し、緯度（float）と経度（float）に変換
    変換できない場合はNoneを返す

    Args:
        gnrmc: GNRMC文字列

    Returns:
        tuple: (緯度, 経度)
    """
    fields = gnrmc.split(",")
    if len(fields) < 10:
        raise ValueError("Invalid GNRMC string")

    raw_latitude, lat_direction = fields[3], fields[4]
    raw_longitude, lon_direction = fields[5], fields[6]

    if not raw_latitude or not lat_direction or not raw_longitude or not lon_direction:
        return None, None

    lat = int(raw_latitude[:2]) + float(raw_latitude[2:]) / 60
    if lat_direction == "S":
        lat = -lat
    lon = int(raw_longitude[:3]) + float(raw_longitude[3:]) / 60
    if lon_direction == "W":
        lon = -lon

    return lat, lon


def get_coordinates(client: ApiClient, project_uuid: str, meas_uuid: str) -> list:
    """
    位置情報取得

    計測のGNSSデータのうち、"#:0/GNRMC"のみ取得
    データポイント（JSONLines形式）ごとの["data"]["s"]（GNRMC形式）をパースして位置情報に変換
    SAMPLE_INTERVALごとにサンプリング

    Args:
        client: APIクライアント
        project_uuid: プロジェクトUUID
        meas_uuid: 計測UUID

    Returns:
        list: 位置情報（緯度・経度）のリスト
    """

    api = measurement_service_data_points_api.MeasurementServiceDataPointsApi(client)
    stream = api.list_project_data_points(
        project_uuid=project_uuid,
        name=meas_uuid,
        data_id_filter=[
            "#:0/GNRMC",  # NMEA
            "#:1/gnss_coordinates",  # intdash Motion
        ],
    )

    coordinates = []
    sample_count = 0
    while True:
        line = stream.readline()
        if not line:
            break

        line_json = json.loads(line.decode())
        if "data" in line_json:
            # iSCPv1 NMEA
            if "s" in line_json["data"]:
                x, y = parse_gnrmc(line_json["data"]["s"])

            # iSCPv2
            elif "d" in line_json["data"]:
                base64_encoded = line_json["data"]["d"]
                bin_data = base64.b64decode(base64_encoded)
                x, y = struct.unpack(">dd", bin_data)

            if x and y and sample_count % SAMPLE_INTERVAL == 0:
                coordinates.append((x, y))
        sample_count += 1

    return coordinates


def calculate_distance(coord1: tuple, coord2: tuple) -> float:
    """
    2点間距離

    Args:
        coord1: (緯度, 経度) 1つ目の座標
        coord2: (緯度, 経度) 2つ目の座標

    Returns:
        float: 距離 (km)
    """
    R = 6371  # 地球の半径
    lat1, lon1 = coord1
    lat2, lon2 = coord2
    dlat = radians(lat2 - lat1)
    dlon = radians(lon2 - lon1)
    a = (
        sin(dlat / 2) ** 2
        + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    )
    return R * 2 * atan2(sqrt(a), sqrt(1 - a))


def total_distance(coordinates: list) -> float:
    """
    総走行距離

    Args:
        coordinates: 座標リスト

    Returns:
        float: 総走行距離 (km)
    """
    return sum(
        calculate_distance(coordinates[i], coordinates[i - 1])
        for i in range(1, len(coordinates))
    )


def main(api_url: str, api_token: str, project_uuid: str, edge_uuids: str) -> None:
    """
    メイン

    - 入力
      - 位置情報取得
        - サーバー負荷軽減のためのスリープ
    - 出力
      - 地図保存
        - jetカラーマップ 0km：青〜250km：赤 で位置情報を点としてマッピング
      - 総走行距離計算

    Args:
        api_url: intdash APIのURL
        api_token: 認証用のAPIトークン
        project_uuid: プロジェクトUUID
        edge_uuids: エッジUUIDリスト
    """

    try:
        # 位置情報取得
        logging.info(
            f"Processing project_uuid: {project_uuid}, edge_uuid: {edge_uuids}"
        )
        client = get_client(api_url, api_token)
        coordinates = []
        for edge_uuid in edge_uuids:
            meas_list = get_meas_list(client, project_uuid, edge_uuid)
            logging.info(
                f"Got measurements list edge_uuid: {edge_uuid}, meas_list: {len(meas_list)}"
            )
            for meas in meas_list:
                meas_uuid = meas["uuid"]
                coordinates.extend(get_coordinates(client, project_uuid, meas_uuid))
                logging.info(f"Added meas: {meas_uuid} coordinates: {len(coordinates)}")
                time.sleep(1)

        # 地図保存
        m = folium.Map(location=ORIGIN, zoom_start=MAP_ZOOM_START)
        for coord in coordinates:
            distance = calculate_distance(ORIGIN, coord)
            distance = NORM(distance)
            color = CMAP(distance)
            color_hex = "#{:02x}{:02x}{:02x}".format(
                int(color[0] * 255), int(color[1] * 255), int(color[2] * 255)
            )
            folium.CircleMarker(
                location=coord,
                radius=CIRCLE_RADIUS,
                color=color_hex,
                fill=True,
                fill_color=color_hex,
                fill_opacity=CIRCLE_OPACITY,
            ).add_to(m)

        map_file = "map.html"
        m.save(map_file)
        logging.info(f"Map saved to {map_file}")

        # 総走行距離計算
        total_dist = total_distance(coordinates)
        logging.info(f"総走行距離: {total_dist:.2f} km")

    except Exception as e:
        logging.error(f"Error: {str(e)}")
        logging.error(traceback.format_exc())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot GSP data on OpenStreetMap")
    parser.add_argument("--api_url", required=True, help="URL of the intdash API")
    parser.add_argument("--api_token", required=True, help="API Token")
    parser.add_argument(
        "--project_uuid",
        default="00000000-0000-0000-0000-000000000000",
        help="Project UUID (default: 00000000-0000-0000-0000-000000000000)",
    )
    parser.add_argument("--edge_uuids", nargs="+", required=True, help="Edge UUID")

    args = parser.parse_args()
    main(args.api_url, args.api_token, args.project_uuid, args.edge_uuids)
