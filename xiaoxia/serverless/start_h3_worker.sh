#!/usr/bin/env bash
set -euo pipefail

export CC="${CC:-/usr/bin/gcc}"
export CXX="${CXX:-/usr/bin/g++}"

if [[ ! -x "$CC" ]]; then
  echo "[H3_BOOT] ERROR: C compiler missing at $CC" >&2
  exit 31
fi
if [[ ! -x "$CXX" ]]; then
  echo "[H3_BOOT] ERROR: C++ compiler missing at $CXX" >&2
  exit 32
fi

echo "[H3_BOOT] compiler ok: CC=$CC CXX=$CXX"
"$CC" --version | head -n 1
"$CXX" --version | head -n 1

echo "[H3_BOOT] resolving RunPod Cached Model"
/usr/bin/python3 /xiaoxia/prepare_h3_models.py

echo "[H3_BOOT] validating MiniMax H3 nodes in pinned ComfyUI"
grep -q "class MiniMaxH3ImageToVideo" /comfyui/comfy_extras/nodes_minimax_h3.py
grep -q "class SaveVideo" /comfyui/comfy_extras/nodes_video.py

# Diagnostic mitigation for H3 hangs on Blackwell/CUDA 13:
# ComfyUI enables comfy-aimdo DynamicVRAM automatically on NVIDIA GPUs.
# The supported ComfyUI switch --disable-dynamic-vram bypasses that path.
# Patch the official worker-comfyui launcher in-place so we preserve RunPod's
# handler/startup behavior while changing only ComfyUI's launch arguments.
echo "[H3_BOOT] applying diagnostic: disable ComfyUI DynamicVRAM/aimdo"
if [[ ! -f /start.sh ]]; then
  echo "[H3_BOOT] ERROR: official /start.sh not found" >&2
  exit 33
fi

python3 - <<'PY'
from pathlib import Path
p = Path("/start.sh")
s = p.read_text()
needle = 'python -u /comfyui/main.py --disable-auto-launch --disable-metadata '
replacement = 'python -u /comfyui/main.py --disable-auto-launch --disable-metadata --disable-dynamic-vram '
count = s.count(needle)
if count < 1:
    raise SystemExit("[H3_BOOT] ERROR: could not locate ComfyUI launch command in /start.sh")
s = s.replace(needle, replacement)
p.write_text(s)
print(f"[H3_BOOT] patched /start.sh launch command(s): {count}")
PY

if ! grep -q -- "--disable-dynamic-vram" /start.sh; then
  echo "[H3_BOOT] ERROR: DynamicVRAM diagnostic flag was not installed" >&2
  exit 34
fi

# Keep ComfyUI verbose so the next run exposes the exact workflow stage if it
# still stalls after DynamicVRAM is disabled.
export COMFY_LOG_LEVEL="${COMFY_LOG_LEVEL:-DEBUG}"
echo "[H3_BOOT] diagnostic active: --disable-dynamic-vram COMFY_LOG_LEVEL=$COMFY_LOG_LEVEL"

echo "[H3_BOOT] starting official worker-comfyui entrypoint"
exec /start.sh
