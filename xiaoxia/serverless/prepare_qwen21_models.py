#!/usr/bin/env python3
"""Prepare ComfyUI model paths for RunPod Cached Model Qwen Image 2.1."""
from __future__ import annotations

import os
from pathlib import Path

HF_CACHE_ROOT = Path("/runpod-volume/huggingface-cache/hub")
MODEL_ID = "Comfy-Org/Qwen-Image-2.1"
MODEL_ROOT = HF_CACHE_ROOT / "models--Comfy-Org--Qwen-Image-2.1"
SNAPSHOTS_DIR = MODEL_ROOT / "snapshots"
EXTRA_MODEL_PATHS = Path("/comfyui/extra_model_paths.yaml")

REQUIRED_FILES = (
    "diffusion_models/qwen_image_2.1_int8_convrot.safetensors",
    "text_encoders/qwen3vl_8b_int8_convrot.safetensors",
    "text_encoders/qwen3.5_9b_qwen_image_2.1_pe_i2i.int8_convrot.safetensors",
    "vae/qwen_image_2.1_vae_bf16.safetensors",
)


def _resolve_snapshot() -> Path:
    requested = (os.environ.get("QWEN21_HF_REVISION") or "").strip()
    if requested:
        candidate = SNAPSHOTS_DIR / requested
        if candidate.is_dir():
            print(f"[QWEN21_MODEL_CACHE] using requested revision={requested}")
            return candidate
        raise RuntimeError(
            f"requested cached revision not found: {candidate}"
        )

    refs_main = MODEL_ROOT / "refs" / "main"
    if refs_main.is_file():
        snapshot_hash = refs_main.read_text(encoding="utf-8").strip()
        candidate = SNAPSHOTS_DIR / snapshot_hash
        if candidate.is_dir():
            print(f"[QWEN21_MODEL_CACHE] using refs/main revision={snapshot_hash}")
            return candidate

    if not SNAPSHOTS_DIR.is_dir():
        raise RuntimeError(f"cached model snapshots directory not found: {SNAPSHOTS_DIR}")

    snapshots = sorted(p for p in SNAPSHOTS_DIR.iterdir() if p.is_dir())
    if len(snapshots) == 1:
        print(f"[QWEN21_MODEL_CACHE] using sole cached snapshot={snapshots[0].name}")
        return snapshots[0]
    if not snapshots:
        raise RuntimeError(f"no cached model snapshots found under: {SNAPSHOTS_DIR}")
    raise RuntimeError(
        "multiple cached snapshots found; set QWEN21_HF_REVISION explicitly"
    )


def main() -> int:
    snapshot = _resolve_snapshot()

    missing = []
    for rel in REQUIRED_FILES:
        path = snapshot / rel
        if not path.is_file():
            missing.append(rel)
        else:
            print(
                f"[QWEN21_MODEL_CACHE] ok file={rel} bytes={path.stat().st_size}"
            )

    if missing:
        raise RuntimeError(
            "cached model is missing required files: " + ", ".join(missing)
        )

    yaml = (
        "xiaoxia_qwen21_cached_model:\n"
        f"  base_path: {snapshot}\n"
        "  diffusion_models: diffusion_models\n"
        "  text_encoders: text_encoders\n"
        "  vae: vae\n"
    )
    EXTRA_MODEL_PATHS.write_text(yaml, encoding="utf-8")
    print(
        f"[QWEN21_MODEL_CACHE] mapped model_id={MODEL_ID} "
        f"snapshot={snapshot.name} config={EXTRA_MODEL_PATHS}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
