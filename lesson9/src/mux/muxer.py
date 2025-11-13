import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass(slots=True)
class MuxInputs:
    """
    多重化設定

    Attributes:
        video (Optional[Path]): 映像入力ファイルパス（.h264）
        audio (Optional[Path]): 音声入力ファイルパス（.wav）
        subtitle (Optional[Path]): 字幕入力ファイルパス（.srt）
    """

    video: Optional[Path] = None
    audio: Optional[Path] = None
    subtitle: Optional[Path] = None


@dataclass(slots=True)
class MuxOptions:
    """
    多重化オプション

    映像・音声・字幕のコーデック指定
    各トラックの“出力MP4に対する先頭位置”

    Attributes:
        v_offset (float): 映像トラックのオフセット [sec]
        a_offset (float): 音声トラックのオフセット [sec]
        s_offset (float): 字幕トラックのオフセット [sec]
        video_fps (Optional[float]): raw H.264（.h264）のFPS
        reencode_video (bool): 映像再エンコード（True=libx264 / False=copy）
        audio_bitrate (str): WAV→AAC 変換時のビットレート
        subtitle_title (str): 字幕トラックのタイトル
        subtitle_lang (str): 字幕トラックの言語コード
    """

    # オフセット（sec）
    v_offset: float = 0.0
    a_offset: float = 0.0
    s_offset: float = 0.0

    # 映像
    video_fps: int = 15
    reencode_video: bool = False

    # 音声
    audio_bitrate: str = "128k"

    # 字幕
    subtitle_title: str = "GNSS"
    subtitle_lang: str = "jpn"


class Muxer:
    """
    トラック多重化

    FFmpeg ラッパ：存在する入力のみ自動選択して MP4 に多重化する。

    Attributes:
        ffmpeg (str): 使用する ffmpeg バイナリ名
    """

    def __init__(self) -> None:
        self.ffmpeg = "ffmpeg"

    def mux(self, out_mp4: Path, inputs: MuxInputs, opts: MuxOptions) -> None:
        """
        多重化

        - video が .h264 の場合は FPS 指定（opts.video_fps or 既定値）を適用
        - audio が .wav の場合は AAC に変換（他は基本 copy）
        - subtitle は .srt を mov_text に変換して埋め込み。`language/title` を付与

        Args:
            out_mp4 (Path): 出力 MP4 ファイルパス
            inputs (MuxInputs): 入力ファイル群
            opts (Optional[MuxOptions]): 多重化オプション

        Raises:
            RuntimeError: 入力が1つも存在しないとき
        """
        tmp_out = out_mp4.with_suffix(".tmp.mp4")
        if tmp_out.exists():
            tmp_out.unlink()

        cmd: List[str] = [self.ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]

        # 入力
        v_idx = a_idx = s_idx = None
        in_count = 0

        # video
        if inputs.video and inputs.video.exists():
            v_idx = in_count
            in_count += 1
            if inputs.video.suffix.lower() == ".h264":
                fps = float(opts.video_fps)
                cmd += [
                    "-r",
                    f"{fps:.6f}",
                    "-fflags",
                    "+genpts",
                    "-itsoffset",
                    f"{opts.v_offset:.6f}",
                    "-i",
                    str(inputs.video),
                ]
            else:
                cmd += ["-itsoffset", f"{opts.v_offset:.6f}", "-i", str(inputs.video)]

        # audio
        if inputs.audio and inputs.audio.exists():
            a_idx = in_count
            in_count += 1
            cmd += ["-itsoffset", f"{opts.a_offset:.6f}", "-i", str(inputs.audio)]

        # subtitle
        if inputs.subtitle and inputs.subtitle.exists():
            s_idx = in_count
            in_count += 1
            cmd += ["-itsoffset", f"{opts.s_offset:.6f}", "-i", str(inputs.subtitle)]

        if in_count == 0:
            raise RuntimeError("no inputs to mux")

        # map / codec
        maps: List[str] = []
        v_args: List[str] = []
        a_args: List[str] = []
        s_args: List[str] = []

        # video
        if v_idx is not None:
            maps += ["-map", f"{v_idx}:v:0"]
            v_args = ["-c:v", ("libx264" if opts.reencode_video else "copy")]

        # audio
        if a_idx is not None:
            maps += ["-map", f"{a_idx}:a:0"]
            if inputs.audio and inputs.audio.suffix.lower() == ".wav":
                a_args = ["-c:a", "aac", "-b:a", opts.audio_bitrate]
            else:
                a_args = ["-c:a", "copy"]

        # subtitle
        if s_idx is not None:
            maps += ["-map", f"{s_idx}:0"]
            s_args = [
                "-c:s",
                "mov_text",
                "-metadata:s:s:0",
                f"language={opts.subtitle_lang}",
                "-metadata:s:s:0",
                f"title={opts.subtitle_title}",
                "-disposition:s:0",
                "default",
            ]

        # 出力
        cmd += maps + v_args + a_args + s_args
        cmd += ["-movflags", "+use_metadata_tags", str(tmp_out)]
        logging.info("[MUX] cmd: %s", " ".join(cmd))

        subprocess.run(cmd, check=True)
        tmp_out.replace(out_mp4)
