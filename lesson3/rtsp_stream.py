import argparse
import asyncio
import logging
import subprocess
import sys
import urllib.parse

import iscp

from lesson3.downstreamer.downstreamer import Downstreamer
from lesson3.logger.delay_logger import DelayLogger
from lesson3.service.rtsp_service import RtspService

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

PORT = 443
RTSP_URL = "rtsp://localhost:8554/stream"
TIME_OFFSET = 9  # 日本
STDERR_FLG = False


async def connect(
    api_url: str,
    api_port: int,
    api_token: str,
    project_uuid: str,
) -> iscp.Conn:
    """
    サーバー接続


    Args:
        api_url (str): APIのURL
        api_port (int): APIのポート
        api_token (str): 認証用のAPIトークン
        project_uuid (str): プロジェクトUUID
    """
    api_url_parsed = urllib.parse.urlparse(api_url)
    conn = await iscp.Conn.connect(
        address=f"{api_url_parsed.hostname}:{api_port}",
        connector=iscp.WebSocketConnector(enable_tls=True),
        token_source=lambda: api_token,
        project_uuid=project_uuid,
    )
    return conn


async def main(api_url: str, api_token: str, project_uuid: str, edge_uuid: str) -> None:
    """
    メイン

    ダウンストリームしたH.264映像データを2つのプロセスに渡す
        ffmpeg:
            標準入力からデータ取得
            再エンコードなし
            RTSPサーバーへストリーム配信
        ffplay（RTSP間との比較用）:
            標準入力からデータ取得
            ウィンドウ表示

    Args:
        api_url (str): 接続するAPIのURL
        api_token (str): 認証用のAPIトークン
        project_uuid (str): プロジェクトのUUID
        edge_uuid (str): エッジデバイスのUUID
    """
    logging.info(
        f"Starting RTSP stream project_uuid: {project_uuid} edge_uuid: {edge_uuid}"
    )

    try:
        service = RtspService(
            Downstreamer(
                await connect(api_url, PORT, api_token, project_uuid),
                edge_uuid,
            ),
            DelayLogger(TIME_OFFSET),
            subprocess.Popen(
                [
                    "ffmpeg",
                    "-f",
                    "h264",
                    "-i",
                    "-",
                    "-fflags",
                    "nobuffer",
                    "-preset",
                    "ultrafast",
                    "-c:v",
                    "copy",  # 再エンコードなし
                    "-f",
                    "rtsp",
                    RTSP_URL,
                ],
                stdin=subprocess.PIPE,
                stderr=sys.stderr if STDERR_FLG else subprocess.DEVNULL,
            ),
            subprocess.Popen(
                [
                    "ffplay",
                    "-f",
                    "h264",
                    "-fflags",
                    "nobuffer",
                    "-flags",
                    "low_delay",
                    "-",
                    "-window_title",
                    "Before RTSP",
                ],
                stdin=subprocess.PIPE,
                stderr=sys.stderr if STDERR_FLG else subprocess.DEVNULL,
            ),
        )
        await service.start()
    except Exception as e:
        logging.error(f"Exception occurred: {e}")
    finally:
        await service.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Process downstream H.264 and RTSP streaming."
    )
    parser.add_argument("--api_url", required=True, help="URL of the intdash API")
    parser.add_argument("--api_token", required=True, help="API Token")
    parser.add_argument(
        "--project_uuid",
        default="00000000-0000-0000-0000-000000000000",
        help="Project UUID (default: 00000000-0000-0000-0000-000000000000)",
    )
    parser.add_argument("--edge_uuid", required=True, help="Edge UUID")

    args = parser.parse_args()

    asyncio.run(main(args.api_url, args.api_token, args.project_uuid, args.edge_uuid))
