import argparse
import asyncio
import logging
import sys
import urllib

import iscp
from chatter.chatter import Chatter
from const.const import (
    DECODE_PIPELINE,
    DOWN_DATA_NAME_H264,
    ENCODE_PIPELINE,
    H264_SIZE,
    JPEG_SIZE,
    PING_INTERVAL,
    PING_TIMEOUT,
    PORT,
    PROMPT_PATH,
    READ_TIMEOUT,
    UP_DATA_NAME_ANSWER,
    UP_DATA_NAME_PREVIEW,
    UP_DATA_NAME_SUMMARY,
)
from convertor.convertor import Convertor
from downstreamer.downstreamer import Downstreamer
from service.summarize_service import SummarizeService
from tiler.tiler import Tiler
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


def load_prompt(path: str) -> str:
    """
    システムプロンプトファイル読込

    Params:
        path (str): システムプロンプトファイルパス

    Returns:
        str: システムプロンプト

    Raises:
        RuntimeError: ファイル読取エラー
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    except Exception as e:
        raise RuntimeError(f"Failed to load prompt file: {path}") from e


async def main(
    api_url: str,
    api_token: str,
    project_uuid: str,
    edge_uuid: str,
    dst_edge_uuid: str,
    openai_key: str,
    prompt_path: str,
) -> None:
    """
    メイン

    ダウンストリームしたH.264映像データを生成AIで要約して
    アップストリームする
        グリッド画像（プレビュー）
        グリッド画像（要約対象）
        要約結果

    Args:
        api_url (str): 接続するAPIのURL
        api_token (str): 認証用のAPIトークン
        project_uuid (str): プロジェクトのUUID
        edge_uuid (str): ダウンストリーム元エッジデバイスのUUID
        dst_edge_uuid (str): アップストリーム先エッジデバイスのUUID
        openai_key (str): OpenAIアクセスキー
        prompt_path (str): システムプロンプトファイルパス
    """
    logging.info(
        f"Starting summarize project_uuid: {project_uuid} edge_uuid: {edge_uuid} dst_edge_uuid: {dst_edge_uuid} prompt_path: {prompt_path}"
    )

    try:
        system_prompt = load_prompt(prompt_path)
        conn = await connect(
            api_url,
            PORT,
            api_token,
            project_uuid,
            edge_uuid,
            PING_INTERVAL,
            PING_TIMEOUT,
        )
        dst_conn = await connect(
            api_url,
            PORT,
            api_token,
            project_uuid,
            dst_edge_uuid,
            PING_INTERVAL,
            PING_TIMEOUT,
        )
        client = get_client(api_url, api_token)
        service = SummarizeService(
            Downstreamer(
                conn,
                edge_uuid,
                [DOWN_DATA_NAME_H264],
            ),
            Convertor(DECODE_PIPELINE),
            Tiler(H264_SIZE[0], H264_SIZE[1], JPEG_SIZE[0], JPEG_SIZE[1]),
            Convertor(ENCODE_PIPELINE),  # プレビュー画像
            MeasurementWriter(client, project_uuid, dst_edge_uuid),
            Upstreamer(
                dst_conn,
                UP_DATA_NAME_PREVIEW,
                UP_DATA_NAME_SUMMARY,
                UP_DATA_NAME_ANSWER,
            ),
            Chatter(openai_key, system_prompt),
            Convertor(ENCODE_PIPELINE),  # 要約対象画像
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
        description="Process downstream H.264, summarize and upstream grid image and answer."
    )
    parser.add_argument("--api_url", required=True, help="URL of the intdash API")
    parser.add_argument("--api_token", required=True, help="API Token")
    parser.add_argument(
        "--project_uuid",
        default="00000000-0000-0000-0000-000000000000",
        help="Project UUID (default: 00000000-0000-0000-0000-000000000000)",
    )
    parser.add_argument("--edge_uuid", required=True, help="Edge UUID")
    parser.add_argument("--dst_edge_uuid", required=False, help="Dest Edge UUID")
    parser.add_argument("--openai_key", required=True, help="OpenAI Access Key")
    parser.add_argument(
        "--prompt_path", default=PROMPT_PATH, help="Sytem prompt file path"
    )

    args = parser.parse_args()

    asyncio.run(
        main(
            args.api_url,
            args.api_token,
            args.project_uuid,
            args.edge_uuid,
            args.dst_edge_uuid if args.dst_edge_uuid else args.edge_uuid,
            args.openai_key,
            args.prompt_path,
        )
    )
