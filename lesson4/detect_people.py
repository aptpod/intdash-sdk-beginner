import argparse
import asyncio
import logging
import sys
import urllib.parse

import iscp

from intdash.api_client import ApiClient
from intdash.configuration import Configuration
from lesson4.convertor.convertor import Convertor
from lesson4.detector.detector import Detector
from lesson4.downstreamer.downstreamer import Downstreamer
from lesson4.service.detect_service import DetectService
from lesson4.upstreamer.upstreamer import Upstreamer
from lesson4.writer.measurement_writer import MeasurementWriter

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

PORT = 443
READ_TIMEOUT = 5 * 60  # 秒
PING_INTERVAL = 10 * 60.0  # 秒
PING_TIMEOUT = 10.0  # 秒

TARGET_SIZE = 640, 480
FPS = 15
BITRATE = 3000  # kbps
KEY_INT_MAX = 30
WEIGHTS_PATH = "./lesson4/yolov4-tiny.weights"
CONFIG_PATH = "./lesson4/yolov4-tiny.cfg"
NAMES_PATH = "./lesson4/coco.names"


# GStreame H.264デコードパイプライン
DECODE_PIPELINE = """
    appsrc name=src is-live=true format=time caps=video/x-h264,stream-format=byte-stream ! 
    h264parse config-interval=-1 ! avdec_h264 ! videoconvert ! video/x-raw,format=BGR !
    appsink name=sink sync=false emit-signals=true
"""

# GStreamer H.264エンコードパイプライン
ENCODE_PIPELINE = """
    appsrc name=src is-live=true format=time caps=video/x-raw,format=BGR,width={width},height={height},framerate={fps}/1 ! 
    videoconvert ! 
    x264enc tune=zerolatency bitrate={bitrate} speed-preset=ultrafast key-int-max={key_int_max} aud=false !
    video/x-h264,stream-format=byte-stream ! 
    appsink name=sink sync=false emit-signals=true
""".format(
    width=TARGET_SIZE[0],
    height=TARGET_SIZE[1],
    fps=FPS,
    bitrate=BITRATE,
    key_int_max=KEY_INT_MAX,
)


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
    サーバー接続


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
    APIクライアント取得

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


async def main(api_url: str, api_token: str, project_uuid: str, edge_uuid: str) -> None:
    """
    メイン

    ダウンストリームしたH.264映像データを物体検出して
    アップストリームする
        矩形描画
        検出数

    Args:
        api_url (str): 接続するAPIのURL
        api_token (str): 認証用のAPIトークン
        project_uuid (str): プロジェクトのUUID
        edge_uuid (str): エッジデバイスのUUID
    """
    logging.info(f"Starting detect project_uuid: {project_uuid} edge_uuid: {edge_uuid}")

    try:
        conn = await connect(
            api_url,
            PORT,
            api_token,
            project_uuid,
            edge_uuid,
            PING_INTERVAL,
            PING_TIMEOUT,
        )
        client = get_client(api_url, api_token)
        service = DetectService(
            Downstreamer(
                conn,
                edge_uuid,
            ),
            Convertor(DECODE_PIPELINE),
            Detector(WEIGHTS_PATH, CONFIG_PATH, NAMES_PATH, TARGET_SIZE),
            Convertor(ENCODE_PIPELINE),
            MeasurementWriter(client, project_uuid, edge_uuid),
            Upstreamer(
                conn,
                edge_uuid,
            ),
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


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process downstream H.264, detect people and upstream H.264 and count."
    )
    parser.add_argument("--api_url", required=True, help="URL of the intdash API")
    parser.add_argument("--api_token", help="API Token")
    parser.add_argument(
        "--project_uuid",
        default="00000000-0000-0000-0000-000000000000",
        help="Project UUID (default: 00000000-0000-0000-0000-000000000000)",
    )
    parser.add_argument("--edge_uuid", required=True, help="Edge UUID")

    args = parser.parse_args()

    asyncio.run(main(args.api_url, args.api_token, args.project_uuid, args.edge_uuid))
