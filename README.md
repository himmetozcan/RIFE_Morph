# RIFE_Morph

Generate `N` RIFE intermediate frames between two images.

This project wraps [`rife-ncnn-vulkan`](https://github.com/nihui/rife-ncnn-vulkan), a portable RIFE build that includes the executable and model files for Windows, Linux, and macOS. It does not require CUDA or PyTorch.

## Quick Start

```bash
git clone https://github.com/himmetozcan/RIFE_Morph.git
cd RIFE_Morph

python rife_morph.py --start path/to/start.png --end path/to/end.png --frames 12 --output output_frames
```

The first run downloads the correct `rife-ncnn-vulkan` release for your OS into `.rife/`. Generated frames are written as:

```text
output_frames/
  000001.png
  000002.png
  ...
  000012.png
```

## Optional Virtual Environment

No Python packages are required, but a venv keeps the project isolated.

macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python rife_morph.py --start start.png --end end.png --frames 8 --output frames
```

Windows PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
py rife_morph.py --start start.png --end end.png --frames 8 --output frames
```

## Examples

Create 24 in-between frames:

```bash
python rife_morph.py --start ./start.png --end ./end.png --frames 24 --output ./morph_frames
```

Overwrite an existing output directory:

```bash
python rife_morph.py --start ./start.png --end ./end.png --frames 24 --output ./morph_frames --overwrite
```

Force CPU mode:

```bash
python rife_morph.py --start ./start.png --end ./end.png --frames 12 --output ./frames --gpu -1
```

Use another bundled model:

```bash
python rife_morph.py --start ./start.png --end ./end.png --frames 12 --model rife-v2.3
```

Use a manually downloaded binary and model:

```bash
python rife_morph.py \
  --start ./start.png \
  --end ./end.png \
  --frames 12 \
  --rife-binary /path/to/rife-ncnn-vulkan \
  --model-path /path/to/models/rife-v4.6
```

## CLI

```text
--start             First/source frame image.
--end               Last/target frame image.
--frames            Number of intermediate frames to generate.
--output            Output directory. Default: output_frames
--format            png, jpg, or webp. Default: png
--model             Bundled model name. Default: rife-v4.6
--model-path        Explicit model directory.
--rife-binary       Explicit rife-ncnn-vulkan executable path.
--gpu               GPU id passed to RIFE. Use -1 for CPU.
--tta-spatial       Enable spatial TTA.
--tta-temporal      Enable temporal TTA.
--uhd               Enable UHD mode.
--overwrite         Replace existing generated frames.
--no-auto-download  Disable automatic RIFE download.
--verbose           Print download and RIFE commands.
```

## Notes

- Start and end frames should be normal image files supported by `rife-ncnn-vulkan`: `jpg`, `png`, or `webp`.
- If the executable fails to start on Linux, install or update your Vulkan driver/runtime from your OS package manager.
- If macOS blocks the downloaded executable, allow it in System Settings, or remove the quarantine attribute from `.rife/` if you trust the downloaded release.
- The script outputs only the generated in-between frames, not copies of the start/end frames.

## Credits

- RIFE: Real-Time Intermediate Flow Estimation for Video Frame Interpolation
- Portable implementation used by this project: [`nihui/rife-ncnn-vulkan`](https://github.com/nihui/rife-ncnn-vulkan)
