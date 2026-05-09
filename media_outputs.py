"""MP4 and GIF encoding helpers for generated RIFE frames."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from rife_backend import run_command


def require_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise SystemExit(
            "ffmpeg is required for --video-output or --gif-output, but it was not found in PATH. "
            "Install ffmpeg or omit those options."
        )
    return ffmpeg


def write_png_sequence(
    ffmpeg: str,
    sequence: list[Path],
    output_dir: Path,
    verbose: bool,
) -> None:
    for index, frame in enumerate(sequence, 1):
        run_command(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(frame),
                "-frames:v",
                "1",
                str(output_dir / f"{index:06d}.png"),
            ],
            verbose=verbose,
        )


def frame_sequence(start: Path, intermediate_frames: list[Path], end: Path) -> list[Path]:
    return [start.expanduser().resolve(), *intermediate_frames, end.expanduser().resolve()]


def encode_video(
    start: Path,
    intermediate_frames: list[Path],
    end: Path,
    video_output: Path,
    fps: int,
    crf: int,
    verbose: bool,
) -> None:
    if fps < 1:
        raise SystemExit("--fps must be at least 1.")
    if not 0 <= crf <= 51:
        raise SystemExit("--crf must be between 0 and 51.")

    ffmpeg = require_ffmpeg()
    video_output = video_output.expanduser().resolve()
    video_output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="rife_morph_video_") as temp_name:
        temp_dir = Path(temp_name)
        write_png_sequence(ffmpeg, frame_sequence(start, intermediate_frames, end), temp_dir, verbose)
        run_command(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-framerate",
                str(fps),
                "-i",
                str(temp_dir / "%06d.png"),
                "-an",
                "-c:v",
                "libx264",
                "-crf",
                str(crf),
                "-vf",
                "pad=ceil(iw/2)*2:ceil(ih/2)*2",
                "-pix_fmt",
                "yuv420p",
                "-r",
                str(fps),
                "-movflags",
                "+faststart",
                str(video_output),
            ],
            verbose=verbose,
        )


def encode_gif(
    start: Path,
    intermediate_frames: list[Path],
    end: Path,
    gif_output: Path,
    fps: int,
    loop: int,
    verbose: bool,
) -> None:
    if fps < 1:
        raise SystemExit("--gif-fps must be at least 1.")
    if loop < 0:
        raise SystemExit("--gif-loop must be 0 or greater.")

    ffmpeg = require_ffmpeg()
    gif_output = gif_output.expanduser().resolve()
    gif_output.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="rife_morph_gif_") as temp_name:
        temp_dir = Path(temp_name)
        write_png_sequence(ffmpeg, frame_sequence(start, intermediate_frames, end), temp_dir, verbose)
        run_command(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-framerate",
                str(fps),
                "-i",
                str(temp_dir / "%06d.png"),
                "-filter_complex",
                "[0:v]split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=bayer:bayer_scale=3",
                "-loop",
                str(loop),
                str(gif_output),
            ],
            verbose=verbose,
        )
