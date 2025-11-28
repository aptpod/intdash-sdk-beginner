import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

from convertor.audio.resampler import Resampler
from convertor.subtitle.reverse_geocoder import ReverseGeocoder
from mux.muxer import Muxer
from reader.measurement_reader import MeasurementReader
from service.download_service import DownloadConfig, DownloadService

from intdash.api_client import ApiClient
from intdash.configuration import Configuration

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

# 抽出データID (intdashの data_id_filter フォーマット)
DATA_ID_AUDIO = ["#:1/pcm"]
DATA_ID_VIDEO = ["#:1/h264"]
DATA_ID_SUBTITLE = ["#:1/gnss_altitude", "#:1/gnss_speed", "#:1/gnss_coordinates"]


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


def main(
    api_url: str,
    api_token: str,
    project_uuid: str,
    meas_uuid: Optional[str],
    edge_uuid: Optional[str],
    start: Optional[str],
    end: Optional[str],
    outdir: Path,
    tracks: list[str],
    fps: int,
    gmap_api_key: Optional[str],
    mux: bool,
) -> None:
    """
    メイン

    meas_uuid を指定 または edge_uuid, start, end の3つを指定

    Args:
        api_url: intdash APIのURL
        api_token: 認証用のAPIトークン
        project_uuid: プロジェクトUUID
        edge_uuid: エッジUUID
        meas_uuid: 計測UUID
        start: 開始時刻
        end: 終了時刻
        outdir: 出力ディレクトリ
        tracks: 出力トラック（audio, video, subtitle）
        fps: 計測データ映像のフレームレート
        gmap_api_key: Google API Key
        mux: トラック統合
    """
    logging.info(
        f"Processing project_uuid: {project_uuid} meas_uuid: {meas_uuid} edge_uuid: {edge_uuid} start: {start} end: {end} outdir: {outdir} tracks: {','.join(tracks)} fps: {fps} mux: {mux}"
    )
    service = None
    try:
        client = get_client(api_url, api_token)

        data_id_filter: list[str] = []
        emit_audio = "audio" in tracks
        if emit_audio:
            data_id_filter.extend(DATA_ID_AUDIO)
            resampler = Resampler()
        emit_video = "video" in tracks
        if emit_video:
            data_id_filter.extend(DATA_ID_VIDEO)
        emit_subtitle = "subtitle" in tracks
        if emit_subtitle:
            data_id_filter.extend(DATA_ID_SUBTITLE)
            geocoder = ReverseGeocoder(gmap_api_key) if gmap_api_key else None

        # 開始
        service = DownloadService(
            DownloadConfig(emit_audio, emit_video, emit_subtitle, outdir, mux=mux),
            MeasurementReader(
                client, project_uuid, edge_uuid, meas_uuid, start, end, data_id_filter
            ),
            resampler if emit_audio else None,
            geocoder if emit_subtitle else None,
            Muxer() if mux else None,
        )
        service.start()
    except Exception as e:
        logging.error(f"Exception occurred: {e}", exc_info=True)
    finally:
        if service:
            service.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Download datapoint and export audio(.wav)/video(.h264)/subtitle(.srt) ."
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
        "--outdir", type=Path, default=Path("./out"), help="Output directory"
    )
    parser.add_argument(
        "--tracks",
        nargs="+",
        choices=["audio", "video", "subtitle"],
        default=["audio", "video", "subtitle"],
        help="Tracks exported",
    )
    parser.add_argument("--fps", type=int, default=15, help="Input H.264 FPS")
    parser.add_argument("--gmap-api-key", default="", help="Google API for subtitle")
    parser.add_argument("--mux", action="store_true", help="Mux tracks to MP4")

    args = parser.parse_args()

    if not (args.meas_uuid or (args.edge_uuid and args.start and args.end)):
        parser.error(
            "Either --meas_uuid must be specified, or --edge_uuid, --start, and --end must all be specified."
        )

    main(
        args.api_url,
        args.api_token,
        args.project_uuid,
        args.meas_uuid,
        args.edge_uuid,
        args.start,
        args.end,
        args.outdir,
        args.tracks,
        args.fps,
        args.gmap_api_key,
        args.mux,
    )
