#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Prepare ComfyUI model paths for MiniMax H3 on RunPod Cached Model.

This file is intentionally NOT wired into the current Qwen worker startup yet.
It is deployment preparation only.  Activate it after the H3 cached-model
layout has been verified in RunPod.

Baseline follows the official Comfy-Org MiniMax H3 I2V template:
- FL2VA pruned INT8 ConvRot diffusion model
- Qwen3-VL-32B NVFP4 AWQ text encoder
- H3 INT8 ConvRot video VAE
- H3 FP32 audio VAE

The existing Qwen 2.1 endpoint may eventually share one ComfyUI worker with H3;
this script therefore appends an H3 model-path stanza rather than replacing
the Qwen stanza when requested by the future worker bootstrap.
"""
from __future__ import annotations

import os
from pathlib import Path

HF_CACHE_ROOT = Path("/runpod-volume/huggingface-cache/hub")
MODEL_ID = "Comfy-Org/MiniMax-H3"
MODEL_ROOT = HF_CACHE_ROOT / "models--Comfy-Org--MiniMax-H3"
SNAPSHOTS_DIR = MODEL_ROOT / "snapshots"

REQUIRED_FILES = (
    "diffusion_models/minimax_h3_fl2va_pruned_int8_convrot.safetensors",
    "text_encoders/qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
    "vae/minimax_h3_video_vae_int8_convrot.safetensors",
    "vae/minimax_h3_audio_vae_fp32.safetensors",
)


def _resolve_snapshot() -> Path:
    requested = (os.environ.get("MINIMAX_H3_HF_REVISION") or "").strip()
    if requested:
        candidate = SNAPSHOTS_DIR / requested
        if candidate.is_dir():
            print(f"[H3_MODEL_CACHE] using requested revision={requested}")
            return candidate
        raise RuntimeError(f"requested cached revision not found: {candidate}")

    refs_main = MODEL_ROOT / "refs" / "main"
    if refs_main.is_file():
        snapshot_hash = refs_main.read_text(encoding="utf-8").strip()
        candidate = SNAPSHOTS_DIR / snapshot_hash
        if candidate.is_dir():
            print(f"[H3_MODEL_CACHE] using refs/main revision={snapshot_hash}")
            return candidate

    if not SNAPSHOTS_DIR.is_dir():
        raise RuntimeError(f"cached model snapshots directory not found: {SNAPSHOTS_DIR}")

    snapshots = sorted(p for p in SNAPSHOTS_DIR.iterdir() if p.is_dir())
    if len(snapshots) == 1:
        print(f"[H3_MODEL_CACHE] using sole cached snapshot={snapshots[0].name}")
        return snapshots[0]
    if not snapshots:
        raise RuntimeError(f"no cached model snapshots found under: {SNAPSHOTS_DIR}")
    raise RuntimeError(
        "multiple cached snapshots found; set MINIMAX_H3_HF_REVISION explicitly"
    )


def validate_snapshot(snapshot: Path) -> None:
    missing: list[str] = []
    for rel in REQUIRED_FILES:
        path = snapshot / rel
        if not path.is_file():
            missing.append(rel)
        else:
            print(f"[H3_MODEL_CACHE] ok file={rel} bytes={path.stat().st_size}")
    if missing:
        raise RuntimeError(
            "cached MiniMax H3 model is missing required files: " + ", ".join(missing)
        )


def model_path_yaml(snapshot: Path) -> str:
    return (
        "xiaoxia_minimax_h3_cached_model:\n"
        f"  base_path: {snapshot}\n"
        "  diffusion_models: diffusion_models\n"
        "  text_encoders: text_encoders\n"
        "  vae: vae\n"
        "  loras: loras\n"
    )


def main() -> int:
    snapshot = _resolve_snapshot()
    validate_snapshot(snapshot)
    print(
        f"[H3_MODEL_CACHE] ready model_id={MODEL_ID} snapshot={snapshot.name}"
    )
    print(model_path_yaml(snapshot), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
