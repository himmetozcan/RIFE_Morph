#!/usr/bin/env python3
"""Generate RIFE intermediate frames between two images.

The script uses the portable rife-ncnn-vulkan executable. On first run it can
download the matching Windows, Linux, or macOS release into .rife/.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from media_outputs import encode_gif, encode_video
from rife_backend import (
    DEFAULT_MODEL,
    ensure_rife,
    generate_frames,
    make_executable,
    resolve_model,
)


def repo_root() -> Path:
    return Path(__file__).resolve().parent


def validate_args(args: argparse.Namespace) -> None:
    if args.frames < 1:
        raise SystemExit("--frames must be at least 1.")
    if args.seamless_hold_frames < 0:
        raise SystemExit("--seamless-hold-frames must be 0 or greater.")
    if args.start == args.end:
        raise SystemExit("--start and --end must point to different files.")
    if args.format not in {"png", "jpg", "webp"}:
        raise SystemExit("--format must be one of: png, jpg, webp.")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fill N RIFE intermediate frames between a start frame and an end frame."
    )
    parser.add_argument("--start", required=True, type=Path, help="First/source frame image.")
    parser.add_argument("--end", required=True, type=Path, help="Last/target frame image.")
    parser.add_argument(
        "--frames",
        required=True,
        type=int,
        help="Number of intermediate frames to generate between start and end.",
    )
    parser.add_argument(
        "--output",
        default=Path("output_frames"),
        type=Path,
        help="Directory where generated frames will be written.",
    )
    parser.add_argument(
        "--format",
        default="png",
        choices=["png", "jpg", "webp"],
        help="Output image format.",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Bundled RIFE model directory name. Default: {DEFAULT_MODEL}.",
    )
    parser.add_argument(
        "--model-path",
        type=Path,
        help="Explicit model directory. Overrides --model.",
    )
    parser.add_argument(
        "--rife-binary",
        type=Path,
        help="Explicit path to rife-ncnn-vulkan executable. Skips auto discovery.",
    )
    parser.add_argument(
        "--gpu",
        help="GPU id passed to rife-ncnn-vulkan. Use -1 for CPU. Default lets RIFE choose.",
    )
    parser.add_argument("--tta-spatial", action="store_true", help="Enable spatial TTA (-x).")
    parser.add_argument("--tta-temporal", action="store_true", help="Enable temporal TTA (-z).")
    parser.add_argument("--uhd", action="store_true", help="Enable UHD mode (-u).")
    parser.add_argument(
        "--video-output",
        type=Path,
        help="Optional MP4 output path. Requires ffmpeg in PATH.",
    )
    parser.add_argument(
        "--gif-output",
        type=Path,
        help="Optional GIF output path. Requires ffmpeg in PATH.",
    )
    parser.add_argument("--fps", type=int, default=24, help="MP4 frame rate. Default: 24.")
    parser.add_argument(
        "--gif-fps",
        type=int,
        help="GIF frame rate. Defaults to --fps.",
    )
    parser.add_argument(
        "--gif-loop",
        type=int,
        default=0,
        help="GIF loop count. 0 means loop forever. Default: 0.",
    )
    parser.add_argument(
        "--crf",
        type=int,
        default=18,
        help="MP4 quality for libx264. Lower is higher quality. Default: 18.",
    )
    parser.add_argument(
        "--seamless",
        action="store_true",
        help="When encoding MP4/GIF, append the same frames in reverse so playback returns to start.",
    )
    parser.add_argument(
        "--seamless-hold-frames",
        type=int,
        default=10,
        help="Endpoint hold frames used by --seamless. Default: 10.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Replace existing output frames.")
    parser.add_argument(
        "--no-auto-download",
        action="store_true",
        help="Do not download rife-ncnn-vulkan automatically.",
    )
    parser.add_argument("--verbose", action="store_true", help="Print download and RIFE commands.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    validate_args(args)

    if args.rife_binary:
        binary = args.rife_binary.expanduser().resolve()
        if not binary.is_file():
            raise SystemExit(f"RIFE binary does not exist: {binary}")
        make_executable(binary)
    else:
        binary = ensure_rife(
            repo_root=repo_root(),
            auto_download=not args.no_auto_download,
            verbose=args.verbose,
        )

    model = resolve_model(binary, args.model, args.model_path)
    outputs = generate_frames(
        start=args.start,
        end=args.end,
        output_dir=args.output,
        frames=args.frames,
        binary=binary,
        model=model,
        image_format=args.format,
        gpu=args.gpu,
        tta_spatial=args.tta_spatial,
        tta_temporal=args.tta_temporal,
        uhd=args.uhd,
        overwrite=args.overwrite,
        verbose=args.verbose,
    )
    if args.video_output:
        encode_video(
            start=args.start,
            intermediate_frames=outputs,
            end=args.end,
            video_output=args.video_output,
            fps=args.fps,
            crf=args.crf,
            seamless=args.seamless,
            seamless_hold_frames=args.seamless_hold_frames,
            verbose=args.verbose,
        )
        print(f"Generated MP4: {args.video_output.expanduser().resolve()}")
    if args.gif_output:
        encode_gif(
            start=args.start,
            intermediate_frames=outputs,
            end=args.end,
            gif_output=args.gif_output,
            fps=args.gif_fps or args.fps,
            loop=args.gif_loop,
            seamless=args.seamless,
            seamless_hold_frames=args.seamless_hold_frames,
            verbose=args.verbose,
        )
        print(f"Generated GIF: {args.gif_output.expanduser().resolve()}")
    print(f"Generated {len(outputs)} frame(s) in {outputs[0].parent}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
