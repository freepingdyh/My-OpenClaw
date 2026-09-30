#!/usr/bin/env bash
set -euo pipefail

echo "[QWEN21_BOOT] resolving RunPod Cached Model"
/usr/bin/python3 /xiaoxia/prepare_qwen21_models.py

echo "[QWEN21_BOOT] syncing fixed reference assets from Zeabur"
/usr/bin/python3 /xiaoxia/fetch_qwen21_assets.py

echo "[QWEN21_BOOT] starting official worker-comfyui entrypoint"
exec /start.sh
