import argparse
import asyncio
import logging
import sys
import urllib

import iscp
from reader.measurement_reader import MeasurementReader
from service.replay_service import ReplayService
from upstreamer.upstreamer import Upstreamer
from writer.measurement_writer import MeasurementWriter

from intdash import ApiClient
from intdash.configuration import Configuration

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

PORT = 443
READ_TIMEOUT = 0.5 * 60.0  # 秒
PING_INTERVAL = 10 * 60.0  # 秒
PING_TIMEOUT = 10.0  # 秒


async def connect(
    api_url: str,
    api_port: int,
    api_token: str,
    project_uuid: str,
    edge_uuid: str,
    ping_interval: float,
    ping_timeout: float,
) -> iscp.Conn:
    """
    リアルタイムAPI接続

    Args:
        api_url (str): APIのURL
        api_port (int): APIのポート
        api_token (str): 認証用のAPIトークン
        project_uuid (str): プロジェクトUUID
        edge_uuid (str): エッジUUID
        ping_interval (float): Ping間隔（秒）
        ping_timeout (float): Pingタイムアウト（秒）
    """
    api_url_parsed = urllib.parse.urlparse(api_url)
    conn = await iscp.Conn.connect(
        address=f"{api_url_parsed.hostname}:{api_port}",
        connector=iscp.WebSocketConnector(enable_tls=True),
        token_source=lambda: api_token,
        project_uuid=project_uuid,
        node_id=edge_uuid,
        ping_interval=ping_interval,
        ping_timeout=ping_timeout,
    )
    return conn


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


async def main(
    src_api_url: str,
    src_api_token: str,
    src_project_uuid: str,
    src_meas_uuid: str,
    src_edge_uuid: str,
    start: str,
    end: str,
    data_id_filter: str,
    dst_api_url: str,
    dst_api_token: str,
    dst_project_uuid: str,
    dst_edge_uuid: str,
    speed: float,
) -> None:
    """
    メイン

    Args:
        src_api_url (str): 元計測データ intdash APIのURL
        src_api_token (str): 元計測データ 認証用のAPIトークン
        src_project_uuid (str): 元計測データ プロジェクトUUID
        src_meas_uuid (str): 元計測データ 元計測UUID
        src_edge_uuid (str): 元計測データ エッジUUID
        start (str): 元計測データ 開始時刻（RFC3339形式）
        end (str): 元計測データ 終了時刻（RFC3339形式）
        data_id_filter (str): 元計測データ データIDフィルター（データ型名:データ名, データ型名:データ名, ..）
        dst_api_url (str): 新計測データ intdash APIのURL
        dst_api_token (str): 新計測データ 認証用のAPIトークン
        dst_project_uuid (str): 新計測データ プロジェクトUUID
        dst_edge_uuid (str): 新計測データ エッジUUID
        speed (float): 再生スピード
    """
    log_args = " ".join([f"{key}: {value}" for key, value in locals().items()])
    logging.info("Processing: " + log_args)

    try:
        conn = await connect(
            dst_api_url,
            PORT,
            dst_api_token,
            dst_project_uuid,
            dst_edge_uuid,
            PING_INTERVAL,
            PING_TIMEOUT,
        )
        src_client = get_client(src_api_url, src_api_token)
        dst_client = get_client(dst_api_url, dst_api_token)
        service = ReplayService(
            MeasurementReader(
                src_client,
                src_project_uuid,
                src_edge_uuid,
                src_meas_uuid,
                start,
                end,
                [s.strip() for s in data_id_filter.split(",")]
                if data_id_filter
                else None,
            ),
            MeasurementWriter(dst_client, dst_project_uuid, dst_edge_uuid),
            Upstreamer(conn),
            speed,
        )
        await service.start(READ_TIMEOUT)

    except iscp.ISCPFailedMessageError as e:
        logging.error(
            f"ISCPFailedMessageError: e.received_message {e.received_message} e.message {e.message}",
            exc_info=True,
        )
    except Exception as e:
        logging.error(f"Exception occurred: {e}", exc_info=True)
    finally:
        await service.close()
        await conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Replay Stored Data as new Measurement Data"
    )
    parser.add_argument("--api_url", required=True, help="URL of intdash API")
    parser.add_argument("--api_token", required=True, help="API Token")
    parser.add_argument(
        "--project_uuid",
        default="00000000-0000-0000-0000-000000000000",
        help="Project UUID",
    )
    parser.add_argument("--meas_uuid", required=False, help="Source Measurement UUID")
    parser.add_argument("--edge_uuid", required=False, help="Source Edge UUID")
    parser.add_argument(
        "--start", required=False, help="Start time yyyy-mm-ddThh:MM:ss.SSSSSS+HH:MM"
    )
    parser.add_argument(
        "--end", required=False, help="End time yyyy-mm-ddThh:MM:ss.SSSSSS+HH:MM"
    )
    parser.add_argument(
        "--data_id_filter", required=False, help="Data ID filter comma separeted"
    )
    parser.add_argument("--dst_api_url", required=False, help="URL of Dest intdash API")
    parser.add_argument("--dst_api_token", required=False, help="Dest API Token")
    parser.add_argument(
        "--dst_project_uuid",
        default="00000000-0000-0000-0000-000000000000",
        help="Project UUID",
    )
    parser.add_argument("--dst_edge_uuid", required=False, help="Dest Edge UUID")
    parser.add_argument("--speed", type=float, default=1, help="Replay speed")

    args = parser.parse_args()

    if not (args.meas_uuid or (args.edge_uuid and args.start and args.end)):
        parser.error(
            "Either --meas_uuid must be specified, or --edge_uuid, --start, and --end must all be specified."
        )
    if not (args.edge_uuid or args.dst_edge_uuid):
        parser.error("Either --edge_uuid or --dst_edge_uuid must be specified.")

    asyncio.run(
        main(
            args.api_url,
            args.api_token,
            args.project_uuid,
            args.meas_uuid,
            args.edge_uuid,
            args.start,
            args.end,
            args.data_id_filter,
            args.dst_api_url if args.dst_api_url else args.api_url,
            args.dst_api_token if args.dst_api_token else args.api_token,
            args.dst_project_uuid,
            args.dst_edge_uuid if args.dst_edge_uuid else args.edge_uuid,
            args.speed,
        )
    )
