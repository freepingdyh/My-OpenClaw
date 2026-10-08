#!/usr/bin/env bash
set -euo pipefail

echo "[H3_BOOT] resolving RunPod Cached Model"
/usr/bin/python3 /xiaoxia/prepare_h3_models.py

echo "[H3_BOOT] validating MiniMax H3 nodes in pinned ComfyUI"
grep -q "class MiniMaxH3ImageToVideo" /comfyui/comfy_extras/nodes_minimax_h3.py
grep -q "class SaveVideo" /comfyui/comfy_extras/nodes_video.py

echo "[H3_BOOT] starting official worker-comfyui entrypoint"
exec /start.sh
