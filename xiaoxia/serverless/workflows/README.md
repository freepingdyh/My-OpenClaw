# Xiaoxia RunPod Serverless

This directory contains code for the RunPod Serverless Qwen Image 2.1 path.

Asset ownership:
- Fixed image_2 through image_6 reference PNGs live in Zeabur persistent storage under `/data/memory/qwen21/refs/`.
- The verified ComfyUI UI workflow lives in Zeabur persistent storage as `/data/memory/qwen21/workflows/xiaoxia_qwen21_special_v1.json`.
- The API-format workflow is generated in Zeabur persistent storage as `/data/memory/qwen21/workflows/xiaoxia_qwen21_special_v1_api.json`.
- Neither workflow nor the fixed refs are stored in this public GitHub repository.

Runtime tooling:
- `convert_qwen21_workflow.py` converts the verified UI workflow into the active API graph and refreshes the SHA256 manifest.
- `fetch_qwen21_assets.py` downloads the five fixed refs from Zeabur's protected asset routes during worker cold start.
- Every ref is checked against `/internal/qwen21/meta/sha256.txt` before it is written to `/comfyui/input`.
- `prepare_qwen21_models.py` maps RunPod Cached Model files into ComfyUI.
- `start_qwen21_worker.sh` prepares cached models, syncs refs, then hands control to the official worker-comfyui `/start.sh`.

The converter intentionally fails closed if the UI workflow enables its prompt-enhancer branch; that branch is disabled in the currently verified workflow.
