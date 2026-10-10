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

echo "[H3_BOOT] starting official worker-comfyui entrypoint"
exec /start.sh
