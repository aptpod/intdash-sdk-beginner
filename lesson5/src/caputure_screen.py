import argparse
import asyncio
import logging
import sys
import urllib.parse
from typing import Optional

import iscp
from convertor.convertor import Convertor
from service.capture_service import CaptureService
from snapper.snapper import Snapper
from upstreamer.upstreamer import Upstreamer
from writer.measurement_writer import MeasurementWriter

from intdash.api_client import ApiClient
from intdash.configuration import Configuration

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

PORT = 443
PING_INTERVAL = 10 * 60.0  # 秒
PING_TIMEOUT = 10.0  # 秒


UP_DATA_NAME = "1/h264"

FPS = 15
BITRATE = 3000  # kbps
KEY_INT_MAX = FPS * 2

# GStreamer H.264エンコードパイプライン
ENCODE_PIPELINE = """
    appsrc name=src is-live=true format=time caps=video/x-raw,format=BGR,width={width},height={height},framerate={fps}/1 !
    videoconvert ! video/x-raw,format=I420 !
    x264enc tune=zerolatency bitrate={bitrate} speed-preset=ultrafast key-int-max={key_int_max} aud=false !
    video/x-h264,stream-format=byte-stream !
    appsink name=sink sync=false emit-signals=true
"""


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
    monitor: int,
    x: int,
    y: int,
    w: Optional[int],
    h: Optional[int],
    up_w: Optional[int],
    up_h: Optional[int],
) -> None:
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
        monitor (int): モニター番号
        x (int): キャプチャ範囲オフセット（左辺）
        y (int): キャプチャ範囲オフセット（上辺）
        w (int): キャプチャ範囲サイズ（幅）
        h (int): キャプチャ範囲サイズ（高さ）
        up_w (int): アップストリームサイズ（幅）
        up_h (int): アップストリームサイズ（高さ）
    """
    logging.info(
        f"Starting capture project_uuid: {project_uuid} edge_uuid: {edge_uuid} monitor: {monitor} x: {x} y: {y} w: {w} h: {h} up_w: {up_w} up_h: {up_h}"
    )

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
        snapper = Snapper(
            monitor,
            (x, y),
            (w, h) if w and h else None,
            (up_w, up_h) if up_w and up_h else None,
        )
        up_w, up_h = snapper.get_resized_size()
        service = CaptureService(
            snapper,
            Convertor(
                ENCODE_PIPELINE.format(
                    width=up_w,
                    height=up_h,
                    fps=FPS,
                    bitrate=BITRATE,
                    key_int_max=KEY_INT_MAX,
                )
            ),
            MeasurementWriter(client, project_uuid, edge_uuid),
            Upstreamer(conn, UP_DATA_NAME),
            FPS,
        )
        await service.start()
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
        description="Process snap screen and upstream H.264."
    )
    parser.add_argument("--api_url", required=True, help="URL of the intdash API")
    parser.add_argument("--api_token", help="API Token")
    parser.add_argument(
        "--project_uuid",
        default="00000000-0000-0000-0000-000000000000",
        help="Project UUID (default: 00000000-0000-0000-0000-000000000000)",
    )
    parser.add_argument("--edge_uuid", required=True, help="Edge UUID")
    parser.add_argument(
        "--monitor", type=int, required=False, default=1, help="Monitors number"
    )
    parser.add_argument(
        "--x", type=int, required=False, default=0, help="Capture offset x"
    )
    parser.add_argument(
        "--y", type=int, required=False, default=0, help="Capture offset y"
    )
    parser.add_argument(
        "--w", type=int, required=False, default=None, help="Capture width"
    )
    parser.add_argument(
        "--h", type=int, required=False, default=None, help="Capture height"
    )
    parser.add_argument(
        "--up_w",
        type=int,
        required=False,
        default=None,
        help="Upstream width",
    )
    parser.add_argument(
        "--up_h",
        type=int,
        required=False,
        default=None,
        help="Upstream height",
    )
    args = parser.parse_args()

    asyncio.run(
        main(
            args.api_url,
            args.api_token,
            args.project_uuid,
            args.edge_uuid,
            args.monitor,
            args.x,
            args.y,
            args.w,
            args.h,
            args.up_w,
            args.up_h,
        )
    )
