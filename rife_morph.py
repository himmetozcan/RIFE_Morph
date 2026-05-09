#!/usr/bin/env python3
"""Generate RIFE intermediate frames between two images.

The script uses the portable rife-ncnn-vulkan executable. On first run it can
download the matching Windows, Linux, or macOS release into .rife/.
"""

from __future__ import annotations

import argparse
import os
import platform
import shutil
import stat
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path


RELEASE_TAG = "20221029"
RELEASE_BASE_URL = (
    "https://github.com/nihui/rife-ncnn-vulkan/releases/download/"
    f"{RELEASE_TAG}"
)
ASSETS = {
    "Darwin": f"rife-ncnn-vulkan-{RELEASE_TAG}-macos.zip",
    "Linux": f"rife-ncnn-vulkan-{RELEASE_TAG}-ubuntu.zip",
    "Windows": f"rife-ncnn-vulkan-{RELEASE_TAG}-windows.zip",
}
DEFAULT_MODEL = "rife-v4.6"
EXECUTABLE_NAME = "rife-ncnn-vulkan.exe" if os.name == "nt" else "rife-ncnn-vulkan"


def repo_root() -> Path:
    return Path(__file__).resolve().parent


def run(command: list[str], *, verbose: bool = False) -> None:
    if verbose:
        print(" ".join(f'"{part}"' if " " in part else part for part in command))
    subprocess.run(command, check=True)


def download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, target.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def make_executable(path: Path) -> None:
    if os.name == "nt":
        return
    current = path.stat().st_mode
    path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def platform_asset() -> str:
    system = platform.system()
    try:
        return ASSETS[system]
    except KeyError as exc:
        supported = ", ".join(sorted(ASSETS))
        raise SystemExit(f"Unsupported OS '{system}'. Supported systems: {supported}.") from exc


def find_executable(root: Path) -> Path | None:
    candidates = sorted(root.rglob(EXECUTABLE_NAME))
    if candidates:
        return candidates[0]
    return None


def ensure_rife(auto_download: bool, verbose: bool) -> Path:
    tools_dir = repo_root() / ".rife"
    existing = find_executable(tools_dir)
    if existing:
        make_executable(existing)
        return existing

    if not auto_download:
        raise SystemExit(
            "rife-ncnn-vulkan was not found under .rife/. "
            "Run without --no-auto-download or pass --rife-binary."
        )

    asset = platform_asset()
    url = f"{RELEASE_BASE_URL}/{asset}"
    archive_path = tools_dir / "downloads" / asset
    extract_dir = tools_dir / asset[:-4]

    if verbose:
        print(f"Downloading {url}")
    download(url, archive_path)

    if extract_dir.exists():
        shutil.rmtree(extract_dir)
    extract_dir.mkdir(parents=True, exist_ok=True)

    if verbose:
        print(f"Extracting {archive_path} -> {extract_dir}")
    with zipfile.ZipFile(archive_path) as archive:
        archive.extractall(extract_dir)

    executable = find_executable(extract_dir)
    if not executable:
        raise SystemExit(f"Could not find {EXECUTABLE_NAME} inside {archive_path}.")
    make_executable(executable)
    return executable


def executable_root(binary: Path) -> Path:
    for parent in [binary.parent, *binary.parents]:
        if (parent / "models").is_dir():
            return parent
        if (parent / DEFAULT_MODEL).is_dir():
            return parent
    return binary.parent


def resolve_model(binary: Path, model_name: str, model_path: Path | None) -> Path:
    if model_path:
        resolved = model_path.expanduser().resolve()
        if not resolved.exists():
            raise SystemExit(f"Model path does not exist: {resolved}")
        return resolved

    root = executable_root(binary)
    search_dirs = [root / "models", root]
    for models_dir in search_dirs:
        model = models_dir / model_name
        if model.exists():
            return model

    available: list[str] = []
    for models_dir in search_dirs:
        if models_dir.exists():
            available.extend(path.name for path in models_dir.iterdir() if path.is_dir())
    available = sorted(set(available))
    suffix = f" Available models: {', '.join(available)}." if available else ""
    raise SystemExit(f"Model '{model_name}' was not found near {binary}.{suffix}")


def validate_args(args: argparse.Namespace) -> None:
    if args.frames < 1:
        raise SystemExit("--frames must be at least 1.")
    if args.start == args.end:
        raise SystemExit("--start and --end must point to different files.")
    if args.format not in {"png", "jpg", "webp"}:
        raise SystemExit("--format must be one of: png, jpg, webp.")


def generate_frames(
    start: Path,
    end: Path,
    output_dir: Path,
    frames: int,
    binary: Path,
    model: Path,
    image_format: str,
    gpu: str | None,
    tta_spatial: bool,
    tta_temporal: bool,
    uhd: bool,
    overwrite: bool,
    verbose: bool,
) -> list[Path]:
    start = start.expanduser().resolve()
    end = end.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()

    if not start.is_file():
        raise SystemExit(f"Start frame does not exist: {start}")
    if not end.is_file():
        raise SystemExit(f"End frame does not exist: {end}")

    output_dir.mkdir(parents=True, exist_ok=True)
    outputs = [output_dir / f"{index:06d}.{image_format}" for index in range(1, frames + 1)]
    existing = [path for path in outputs if path.exists()]
    if existing and not overwrite:
        raise SystemExit(
            f"{len(existing)} output frame(s) already exist in {output_dir}. "
            "Use --overwrite to replace them."
        )

    for index, output in enumerate(outputs, 1):
        step = index / (frames + 1)
        command = [
            str(binary),
            "-0",
            str(start),
            "-1",
            str(end),
            "-o",
            str(output),
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
        run(command, verbose=verbose)

    return outputs


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
        binary = ensure_rife(auto_download=not args.no_auto_download, verbose=args.verbose)

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
    print(f"Generated {len(outputs)} frame(s) in {outputs[0].parent}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted.", file=sys.stderr)
        raise SystemExit(130)
