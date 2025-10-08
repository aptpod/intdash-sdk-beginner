import argparse
import asyncio
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from convertor.convertor import Convertor
from service.upload_service import UploadService
from writer.measurement_writer import MeasurementWriter

from intdash.api_client import ApiClient
from intdash.configuration import Configuration

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# 定数
FETCH_SIZE = 100

# GStreamer パイプライン
PIPELINE = """
    filesrc location="{path}" !
    qtdemux name=demux demux.video_0 !
    h264parse config-interval=-1 !
    video/x-h264,stream-format=byte-stream,alignment=au !
    appsink name=sink sync=false emit-signals=true
"""


def get_client(api_url: str, api_token: str) -> ApiClient:
    """
    REST API設定

    Args:
        api_url (str): APIのURL
        api_token (str): APIトークン
    Returns:
        ApiClient: APIクライアント
    """
    configuration = Configuration(
        host=f"{api_url}/api", api_key={"IntdashToken": api_token}
    )
    client = ApiClient(configuration)
    return client


async def main(
    api_url: str,
    api_token: str,
    project_uuid: str,
    edge_uuid: str,
    filepath: Path,
    data_name: str,
    basetime: str,
) -> None:
    """
    メイン

    Args:
        api_url: intdash APIのURL
        api_token: 認証用のAPIトークン
        project_uuid: プロジェクトUUID
        edge_uuid: エッジUUID
        filepath: MP4ファイルパス
        data_name: データ名
        basetime: 基準時刻
    """
    logging.info(
        f"Processing project_uuid: {project_uuid}, edge_uuid: {edge_uuid} filepath: {filepath} data_name: {data_name} basetime: {basetime}"
    )

    try:
        client = get_client(api_url, api_token)
        service = UploadService(
            Convertor(PIPELINE.format(path=filepath)),
            MeasurementWriter(client, project_uuid, edge_uuid),
            FETCH_SIZE,
        )
        await service.start(
            filepath,
            data_name,
            datetime.fromisoformat(basetime)
            if basetime
            else datetime.now(tz=timezone.utc),
        )

    except Exception as e:
        logging.error(f"Exception occurred: {e}", exc_info=True)
    finally:
        await service.close()
        pass


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process read MP4 frame, put it and count."
    )
    parser.add_argument("--api_url", required=True, help="URL of the intdash API")
    parser.add_argument("--api_token", required=True, help="API Token")
    parser.add_argument(
        "--project_uuid",
        default="00000000-0000-0000-0000-000000000000",
        help="Project UUID (default: 00000000-0000-0000-0000-000000000000)",
    )
    parser.add_argument("--edge_uuid", required=True, help="Edge UUID")

    parser.add_argument(
        "--src_path", type=Path, required=True, help="Input MP4 file path"
    )
    parser.add_argument(
        "--data_name",
        default="video/h264",
        help="Data name (default: video/h264)",
    )
    parser.add_argument(
        "--basetime",
        default=None,
        help="Base time (RFC3339, e.g. 2025-01-02T12:34:56.789+09:00 or ...Z)",
    )

    args = parser.parse_args()

    asyncio.run(
        main(
            args.api_url,
            args.api_token,
            args.project_uuid,
            args.edge_uuid,
            args.src_path,
            args.data_name,
            args.basetime,
        )
    )
