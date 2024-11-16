import argparse
import logging
import sys
import traceback

from intdash import ApiClient
from intdash.configuration import Configuration
from lesson2.distance.calculator.distance_calculator import DistanceCalculator
from lesson2.distance.reader.measurement_reader import MeasurementReader
from lesson2.distance.service.distance_service import DistanceService
from lesson2.distance.writer.measurement_writer import MeasurementWriter

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
            project_uuid,
            meas_uuid,
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
        description="Process measurement data and output to JSON."
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
