"""Video FPS upsampling with RIFE intermediate frames."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from media_outputs import require_ffmpeg
from rife_backend import run_command


def extract_video_frames(
    input_video: Path,
    frames_dir: Path,
    source_fps: int,
    verbose: bool,
) -> list[Path]:
    frames_dir.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            require_ffmpeg(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(input_video),
            "-vf",
            f"fps={source_fps}",
            str(frames_dir / "%06d.png"),
        ],
        verbose=verbose,
    )
    frames = sorted(frames_dir.glob("*.png"))
    if len(frames) < 2:
        raise SystemExit("Need at least two video frames for RIFE FPS upsampling.")
    return frames


def encode_png_sequence(
    frames_dir: Path,
    output_video: Path,
    fps: int,
    crf: int,
    verbose: bool,
) -> None:
    output_video.parent.mkdir(parents=True, exist_ok=True)
    run_command(
        [
            require_ffmpeg(),
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(frames_dir / "%06d.png"),
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
            str(output_video),
        ],
        verbose=verbose,
    )


def interpolate_video_fps(
    input_video: Path,
    output_video: Path,
    source_fps: int,
    target_fps: int,
    binary: Path,
    model: Path,
    gpu: str | None,
    tta_spatial: bool,
    tta_temporal: bool,
    uhd: bool,
    crf: int,
    overwrite: bool,
    verbose: bool,
) -> None:
    if source_fps < 1:
        raise SystemExit("--source-fps must be at least 1.")
    if target_fps <= source_fps:
        raise SystemExit("--target-fps must be greater than --source-fps.")
    if target_fps % source_fps != 0:
        raise SystemExit("Video FPS mode currently requires target FPS to be an integer multiple of source FPS.")
    if not 0 <= crf <= 51:
        raise SystemExit("--crf must be between 0 and 51.")

    input_video = input_video.expanduser().resolve()
    output_video = output_video.expanduser().resolve()
    if not input_video.is_file():
        raise SystemExit(f"Input video does not exist: {input_video}")
    if output_video.exists() and not overwrite:
        raise SystemExit(f"Output video already exists: {output_video}. Use --overwrite to replace it.")

    multiplier = target_fps // source_fps
    with tempfile.TemporaryDirectory(prefix="rife_video_fps_") as temp_name:
        temp = Path(temp_name)
        input_frames = extract_video_frames(input_video, temp / "input", source_fps, verbose)
        output_frames = temp / "output"
        output_frames.mkdir(parents=True, exist_ok=True)

        out_index = 1
        for frame_index, current in enumerate(input_frames[:-1]):
            nxt = input_frames[frame_index + 1]
            shutil.copy2(current, output_frames / f"{out_index:06d}.png")
            out_index += 1

            for step_index in range(1, multiplier):
                step = step_index / multiplier
                out = output_frames / f"{out_index:06d}.png"
                command = [
                    str(binary),
                    "-0",
                    str(current),
                    "-1",
                    str(nxt),
                    "-o",
                    str(out),
                    "-s",
                    f"{step:.8f}",
                    "-m",
                    str(model),
                ]
                if gpu is not None:
                    command.extend(["-g", gpu])
                if tta_spatial:
                    command.append("-x")
                if tta_temporal:
                    command.append("-z")
                if uhd:
                    command.append("-u")
                run_command(command, verbose=verbose)
                out_index += 1

        last = input_frames[-1]
        for _ in range(multiplier):
            shutil.copy2(last, output_frames / f"{out_index:06d}.png")
            out_index += 1

        encode_png_sequence(output_frames, output_video, target_fps, crf, verbose)
