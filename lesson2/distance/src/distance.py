import argparse
import logging
import sys
import traceback

from calculator.distance_calculator import DistanceCalculator
from reader.measurement_reader import MeasurementReader
from service.distance_service import DistanceService
from writer.measurement_writer import MeasurementWriter

from intdash import ApiClient
from intdash.configuration import Configuration

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# 定数
FETCH_SIZE = 100
ORIGIN = (35.628222, 139.738694)  # 品川駅


def get_client(api_url: str, api_token: str) -> ApiClient:
    """
    REST API設定

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


def main(api_url: str, api_token: str, project_uuid: str, meas_uuid: str) -> None:
    """
    メイン

    Args:
        api_url: intdash APIのURL
        api_token: 認証用のAPIトークン
        project_uuid: プロジェクトUUID
        meas_uuid: 元計測UUID
    """
    logging.info(f"Processing project_uuid: {project_uuid}, meas_uuid: {meas_uuid}")

    try:
        client = get_client(api_url, api_token)
        service = DistanceService(
            MeasurementReader(client, project_uuid, meas_uuid),
            DistanceCalculator(ORIGIN),
            MeasurementWriter(client, project_uuid),
            FETCH_SIZE,
        )
        service.process()

    except Exception as e:
        logging.error(f"Error: {str(e)}")
        logging.error(traceback.format_exc())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process get GNSS, caliculate distance and put it and count."
    )
    parser.add_argument("--api_url", required=True, help="URL of the intdash API")
    parser.add_argument("--api_token", required=True, help="API Token")
    parser.add_argument(
        "--project_uuid",
        default="00000000-0000-0000-0000-000000000000",
        help="Project UUID (default: 00000000-0000-0000-0000-000000000000)",
    )
    parser.add_argument("--meas_uuid", required=True, help="Measurement UUID")

    args = parser.parse_args()
    main(args.api_url, args.api_token, args.project_uuid, args.meas_uuid)
