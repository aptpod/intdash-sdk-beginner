import logging
import os
import sys
import traceback
from typing import Any, Dict

from calculator.distance_calculator import DistanceCalculator
from notifier.notifier import Notifier
from reader.measurement_reader import MeasurementReader
from service.distance_service import DistanceService
from writer.measurement_writer import MeasurementWriter

from intdash import ApiClient
from intdash.configuration import Configuration

# ログ設定
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)


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


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    エントリポイント

    環境変数取得
    イベント情報取得
    距離算出サービス起動

    Args:
        event (dict): Lambdaイベントオブジェクト
        context (LambdaContext): Lambdaコンテキストオブジェクト
    """
    api_url = os.getenv("API_URL", "https://example.intdash.jp")
    api_token = os.getenv("API_TOKEN", "<YOUR_API_TOKEN>")
    fetch_size = int(os.getenv("FETCH_SIZE", 100))
    origin_lat = float(os.getenv("ORIGIN_LAT", 35.6878973))
    origin_lon = float(os.getenv("ORIGIN_LON", 139.7170926))
    origin = (origin_lat, origin_lon)  # 会社
    slack_url = os.getenv("SLACK_URL", "<YOUR_SLACK_WEBHOOK_URL>")

    project_uuid = event.get("project_uuid")
    meas_uuid = event.get("measurement_uuid")

    if not api_url or not api_token or not project_uuid or not meas_uuid:
        logging.error("Missing required parameters in the event.")
        return {"statusCode": 400, "body": "Missing required parameters."}

    logging.info(f"Processing project_uuid: {project_uuid}, meas_uuid: {meas_uuid}")

    try:
        client = get_client(api_url, api_token)
        service = DistanceService(
            MeasurementReader(client, project_uuid, meas_uuid),
            DistanceCalculator(origin),
            MeasurementWriter(client, project_uuid),
            fetch_size,
            Notifier(api_url, slack_url, project_uuid),
        )
        service.process()

        return {"statusCode": 200, "body": "Processing completed successfully."}

    except Exception as e:
        logging.error(f"Error: {str(e)}")
        logging.error(traceback.format_exc())
        return {"statusCode": 500, "body": "Internal server error."}
