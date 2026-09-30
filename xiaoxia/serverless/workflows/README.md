# Xiaoxia RunPod Serverless

This directory contains code for the RunPod Serverless Qwen Image 2.1 path.

Asset ownership:
- Fixed image_2 through image_6 reference PNGs live in Zeabur persistent storage under `/data/memory/qwen21/refs/`.
- The ComfyUI source workflow JSON lives in Zeabur persistent storage under `/data/memory/qwen21/workflows/`.
- Neither the fixed refs nor workflow JSON are stored in this public GitHub repository.

Runtime staging:
- `fetch_qwen21_assets.py` downloads the five fixed refs from Zeabur's protected asset routes during worker cold start.
- Every ref is checked against `/internal/qwen21/meta/sha256.txt` before it is written to `/comfyui/input`.
- `start_qwen21_worker.sh` performs that sync and then hands control to the official worker-comfyui `/start.sh`.

The API-format ComfyUI workflow is intentionally not committed here until conversion/export from the verified source workflow has been completed and tested.
