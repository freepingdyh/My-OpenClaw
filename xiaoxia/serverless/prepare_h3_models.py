#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prepare ComfyUI model paths for MiniMax H3 from a RunPod Global Volume.

Serverless Global Volumes mount at /runpod-volume.  The H3 files are kept in a
dedicated /runpod-volume/h3_models tree so they can coexist with unrelated
assets already stored on xiaoxia-models.

Expected layout:
  /runpod-volume/h3_models/
    diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors
    text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors
    vae/minimax_h3_video_vae_int8_convrot.safetensors
    vae/minimax_h3_audio_vae_fp32.safetensors

This script only validates and maps existing files.  It never downloads model
weights during Serverless startup.
"""
from __future__ import annotations

from pathlib import Path

MODEL_ROOT = Path("/runpod-volume/h3_models")
EXTRA_MODEL_PATHS = Path("/comfyui/extra_model_paths.yaml")

REQUIRED_FILES = (
    "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors",
    "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
    "vae/minimax_h3_video_vae_int8_convrot.safetensors",
    "vae/minimax_h3_audio_vae_fp32.safetensors",
)


def validate_volume() -> None:
    if not MODEL_ROOT.is_dir():
        raise RuntimeError(
            f"H3 Global Volume directory not found: {MODEL_ROOT}. "
            "Attach xiaoxia-models to this endpoint and populate h3_models first."
        )

    missing: list[str] = []
    for rel in REQUIRED_FILES:
        path = MODEL_ROOT / rel
        if not path.is_file():
            missing.append(rel)
        else:
            print(f"[H3_GLOBAL_VOLUME] ok file={rel} bytes={path.stat().st_size}")

    if missing:
        raise RuntimeError(
            "H3 Global Volume is missing required files: " + ", ".join(missing)
        )


def model_path_yaml() -> str:
    return (
        "xiaoxia_minimax_h3_global_volume:\n"
        f"  base_path: {MODEL_ROOT}\n"
        "  diffusion_models: diffusion_models\n"
        "  text_encoders: text_encoders\n"
        "  vae: vae\n"
    )


def main() -> int:
    validate_volume()
    EXTRA_MODEL_PATHS.write_text(model_path_yaml(), encoding="utf-8")
    print(
        f"[H3_GLOBAL_VOLUME] mapped root={MODEL_ROOT} "
        f"config={EXTRA_MODEL_PATHS}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
