"""RIFE binary setup and intermediate-frame generation."""

from __future__ import annotations

import os
import platform
import shutil
import stat
import subprocess
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


def run_command(command: list[str], *, verbose: bool = False) -> None:
    if verbose:
        print(" ".join(f'"{part}"' if " " in part else part for part in command))
    try:
        subprocess.run(command, check=True)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(f"Command failed with exit code {exc.returncode}: {command[0]}") from exc


def make_executable(path: Path) -> None:
    if os.name == "nt":
        return
    current = path.stat().st_mode
    path.chmod(current | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def ensure_rife(repo_root: Path, auto_download: bool, verbose: bool) -> Path:
    tools_dir = repo_root / ".rife"
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


def find_executable(root: Path) -> Path | None:
    candidates = sorted(root.rglob(EXECUTABLE_NAME))
    if candidates:
        return candidates[0]
    return None


def platform_asset() -> str:
    system = platform.system()
    try:
        return ASSETS[system]
    except KeyError as exc:
        supported = ", ".join(sorted(ASSETS))
        raise SystemExit(f"Unsupported OS '{system}'. Supported systems: {supported}.") from exc


def download(url: str, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url) as response, target.open("wb") as handle:
        shutil.copyfileobj(response, handle)


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
        run_command(command, verbose=verbose)

    return outputs
