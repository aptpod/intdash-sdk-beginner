import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import numpy as np
from convertor.audio.codec import decode_pcm_s16le, encode_pcm_s16le
from convertor.audio.resampler import Resampler
from convertor.subtitle.aggregator import Aggregator, SrtSegment
from convertor.subtitle.reverse_geocoder import ReverseGeocoder
from mux.muxer import Muxer, MuxInputs, MuxOptions
from reader.measurement_reader import MeasurementReader
from writer.bin_writer import BinWriter
from writer.srt_writer import SrtWriter
from writer.wav_writer import WavWriter


@dataclass(slots=True)
class DownloadConfig:
    """
    ダウンロード設定

    Attributes:
        emit_audio (bool): 音声トラック出力
        emit_video (bool): 映像トラック出力
        emit_subtitle (bool): 字幕トラック出力
        outdir (Path): 出力ディレクトリ
        audio_name (str): 出力WAVファイル名
        video_name (str): 出力H.264ファイル名
        srt_name (str): 出力SRTファイル名
        fps (int): 映像フレームレート（.h264入力のみ使用）
        mux (bool): MP4多重化
    """

    emit_audio: bool = True
    emit_video: bool = True
    emit_subtitle: bool = True
    outdir: Path = Path("./out")
    audio_name: str = "audio.wav"
    video_name: str = "video.h264"
    srt_name: str = "subtitle.srt"
    mp4_name: str = "out.mp4"
    fps: int = 15
    mux: bool = False


class DownloadService:
    """
    ダウンロードサービス

    計測データを逐次処理して音声/映像/字幕を生成し、任意でMP4に多重化する

    Attributes:
        cfg (DownloadConfig): 出力設定
        reader (MeasurementReader): 計測取得
        resampler (Resampler): 音声リサンプラー
        geocoder (ReverseGeocoder): 逆ジオコーダー
        muxer (Muxer): MP4統合
        _wav (WavWriter): WAVファイル出力
        _h264 (BinWriter): H.264ファイル出力
        _srt (SrtWriter): SRTファイル出力
        _t0_audio (float): 音声の先頭相対時刻[s]
        _t0_video (float): 映像の先頭相対時刻[s]
        _t0_sub (float): 字幕の先頭相対時刻[s]
        _t_last (float): 最終相対時刻[s]
    """

    def __init__(
        self,
        cfg: DownloadConfig,
        reader: MeasurementReader,
        resampler: Optional[Resampler],
        geocoder: Optional[ReverseGeocoder],
        muxer: Optional[Muxer],
    ) -> None:
        self.cfg = cfg
        self.reader = reader

        # audio
        self.resampler = resampler

        # subtitle
        self.geocoder = geocoder

        # mux
        self.muxer = muxer

        # writers
        self._wav: Optional[WavWriter] = None
        self._h264: Optional[BinWriter] = None
        self._srt: Optional[SrtWriter] = None

        # 各トラックの先頭時刻（s）
        self._t0_audio: Optional[float] = None
        self._t0_video: Optional[float] = None
        self._t0_sub: Optional[float] = None

        # 最終時刻
        self._t_last: float = 0.0

    def start(self) -> None:
        """
        開始

        計測データを逐次処理して各トラックを出力

        動作:
            - 元計測の基準時刻取得
            - 出力ファイルオープン
            - データポイント逐次処理
              - PCMはデコード・リサンプル・エンコードしてWAV出力
              - H.264は生バイナリで出力
              - GNSSはテロップ単位に集約して定期(tick)テキスト出力
                - 最終セグメントをクローズ
            - mux 指定時は MP4 に多重化

        Raises:
            RuntimeError: 必須ライター/リサンプラが None の場合
        """

        # 元計測の基準時刻取得
        bt = self.reader.get_basetime()
        basetime = int(bt.timestamp() * 1e9)
        aggregator = Aggregator()

        # 出力ファイルオープン
        self._open_writers()

        # データポイント逐次処理
        for t_ns, _, data_name, data_bytes in self.reader.get_datapoints():
            t_rel = (t_ns - basetime) * 1e-9
            if t_rel < 0:
                continue

            # ------- PCM -------
            if data_name == "1/pcm":
                if self.resampler is None:
                    raise RuntimeError
                if self._wav is None:
                    raise RuntimeError
                f32 = decode_pcm_s16le(data_bytes)  # bytes -> float32
                f32_out = self.resampler.push_block(t_rel, f32)
                if f32_out.size:
                    i16 = encode_pcm_s16le(f32_out)  # float32 -> bytes
                    self._wav.write(i16)
                    if self._t0_audio is None:
                        self._t0_audio = t_rel

            # ------- H.264 -------
            elif data_name == "1/h264":
                if self._h264 is None:
                    raise RuntimeError
                self._h264.write(data_bytes)
                if self._t0_video is None:
                    self._t0_video = t_rel

            # ------- GNSS: speed -------
            elif data_name == "1/gnss_speed":
                if len(data_bytes) >= 8:
                    v = np.frombuffer(data_bytes[:8], dtype=">f8")[0]
                    v = round(v, 1)
                    aggregator.update_speed(v)

            # ------- GNSS: altitude [tick] -------
            elif data_name == "1/gnss_altitude":
                if len(data_bytes) >= 8:
                    alt = np.frombuffer(data_bytes[:8], dtype=">f8")[0]
                    alt = round(alt, 1)
                    aggregator.update_altitude(alt)
                    seg = aggregator.on_tick(t_rel)  # 高度は約1Hz
                    if seg:
                        self._write_segment(seg)
                        if self._t0_sub is None:
                            self._t0_sub = seg.start

            # ------- GNSS: coordinates-------
            elif data_name == "1/gnss_coordinates":
                if len(data_bytes) >= 16:
                    lat, lon = np.frombuffer(data_bytes[:16], dtype=">f8")
                    changed, lat_q, lon_q = aggregator.update_latlon(lat, lon)

                    # セルが変わった時だけ逆ジオコーディング
                    if changed and self.geocoder is not None:
                        addr = self.geocoder.lookup(lat_q, lon_q)
                        if addr:
                            aggregator.update_address(addr)

            self._t_last = max(self._t_last, t_rel)

        # 最終セグメント
        if self.cfg.emit_subtitle:
            seg = aggregator.finalize(self._t_last)
            if seg:
                self._write_segment(seg)
                if self._t0_sub is None:
                    self._t0_sub = seg.start

        self._close_writers()

        # mux
        if self.cfg.mux:
            self._run_mux()

    # ---- internal --------------------------------------------------------
    def _open_writers(self) -> None:
        """
        出力ファイルオープン

        出力ファイルがなければ作成
        """
        outdir = self.cfg.outdir
        outdir.mkdir(parents=True, exist_ok=True)
        if self.cfg.emit_audio:
            self._wav = WavWriter(outdir / self.cfg.audio_name, nch=1)
            self._wav.open()
        if self.cfg.emit_video:
            self._h264 = BinWriter(outdir / self.cfg.video_name)
            self._h264.open()
        if self.cfg.emit_subtitle:
            self._srt = SrtWriter(outdir / self.cfg.srt_name)
            self._srt.open()

    def _write_segment(self, seg: SrtSegment) -> None:
        """
        字幕セグメント出力

        Raises:
            RuntimeError: ライターが None の場合
        """
        if self._srt is None:
            raise RuntimeError
        self._srt.write(seg.start, seg.end, seg.line1, seg.line2)

    def _close_writers(self) -> None:
        """
        出力ファイルクローズ
        """
        if self._wav:
            self._wav.close()
            logging.info(f"[AUDIO] Exported WAV file: {self._wav.path}")
        if self._h264:
            self._h264.close()
            logging.info(f"[VIDEO] Exported H.264 file: {self._h264.path}")
        if self._srt:
            self._srt.close()
            logging.info(f"[SRT] Exported SRT file: {self._srt.path}")

    def _run_mux(self) -> None:
        """
        MP4多重化

        生成済みの H.264 / WAV / SRT を MP4 に多重化

        動作:
            - 出力トラック設定
            - 各トラックの先頭相対時刻からオフセット算出
            - 多重化

        Raises:
            RuntimeError: muxer が None の場合
        """
        if self.muxer is None:
            raise RuntimeError

        # 出力トラック設定
        v = (self.cfg.outdir / self.cfg.video_name) if self.cfg.emit_video else None
        a = (self.cfg.outdir / self.cfg.audio_name) if self.cfg.emit_audio else None
        s = (self.cfg.outdir / self.cfg.srt_name) if self.cfg.emit_subtitle else None
        inputs = MuxInputs(
            video=v if (v and v.exists()) else None,
            audio=a if (a and a.exists()) else None,
            subtitle=s if (s and s.exists()) else None,
        )

        # 各トラックの先頭相対時刻からオフセット算出
        t0s = [
            t for t in (self._t0_video, self._t0_audio, self._t0_sub) if t is not None
        ]
        t_min = min(t0s) if t0s else 0.0
        v_off = (self._t0_video or 0.0) - t_min
        a_off = (self._t0_audio or 0.0) - t_min
        s_off = (self._t0_sub or 0.0) - t_min
        opts = MuxOptions(
            video_fps=self.cfg.fps,
            v_offset=v_off,
            a_offset=a_off,
            s_offset=s_off,
            subtitle_title="GNSS",
            subtitle_lang="jpn",
        )

        # 多重化
        out_mp4 = Path(self.cfg.outdir / self.cfg.mp4_name)
        self.muxer.mux(out_mp4=out_mp4, inputs=inputs, opts=opts)
        logging.info(f"[MUX] Muxed MP4 file: {out_mp4}")

    def close(self) -> None:
        """
        終了
        """
        pass
