#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""H3-specific RunPod handler shim.

RunPod's stock worker-comfyui handler currently only collects media exposed
through history output nodes under the "images" key. ComfyUI's native
SaveVideo may successfully write an MP4 while the stock handler reports
"Processing 0 output nodes" / success_no_images.

This shim delegates all job execution to the stock handler first, then, only
when it returned no media, detects a video file newly created in ComfyUI's
output tree during this job and returns it through the existing output.images[]
transport so the Xiaoxia client does not need a second response schema.
"""
from __future__ import annotations

import base64
import importlib.util
import os
from pathlib import Path
from typing import Any

import runpod

BASE_HANDLER_PATH = Path("/handler_base.py")
OUTPUT_ROOT = Path(os.environ.get("COMFY_OUTPUT_PATH", "/comfyui/output"))
VIDEO_EXTENSIONS = {".mp4", ".webm", ".mov", ".mkv"}


def _load_base_handler():
    spec = importlib.util.spec_from_file_location("worker_comfyui_base_handler", BASE_HANDLER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load stock worker handler: {BASE_HANDLER_PATH}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


base_handler = _load_base_handler()


def _video_snapshot() -> dict[str, int]:
    snapshot: dict[str, int] = {}
    if not OUTPUT_ROOT.exists():
        return snapshot
    for path in OUTPUT_ROOT.rglob("*"):
        try:
            if path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS:
                snapshot[str(path)] = path.stat().st_mtime_ns
        except OSError:
            continue
    return snapshot


def _newest_changed_video(before: dict[str, int]) -> Path | None:
    candidates: list[tuple[int, Path]] = []
    if not OUTPUT_ROOT.exists():
        return None
    for path in OUTPUT_ROOT.rglob("*"):
        try:
            if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
                continue
            mtime_ns = path.stat().st_mtime_ns
            previous = before.get(str(path))
            if previous is None or mtime_ns > previous:
                candidates.append((mtime_ns, path))
        except OSError:
            continue
    if not candidates:
        return None
    candidates.sort(key=lambda row: row[0], reverse=True)
    return candidates[0][1]


def _has_media(result: Any) -> bool:
    if not isinstance(result, dict):
        return False
    images = result.get("images")
    return isinstance(images, list) and len(images) > 0


def handler(job: dict[str, Any]) -> dict[str, Any]:
    before = _video_snapshot()
    result = base_handler.handler(job)

    # Preserve normal stock-worker results verbatim.
    if _has_media(result):
        return result

    video_path = _newest_changed_video(before)
    if video_path is None:
        if isinstance(result, dict):
            return result
        return {"error": "H3 worker returned no structured result and no new video file"}

    try:
        blob = video_path.read_bytes()
    except Exception as exc:
        return {
            "error": "H3 video was generated but could not be read",
            "details": [f"{type(exc).__name__}: {exc}", str(video_path)],
        }

    if not blob:
        return {
            "error": "H3 video file is empty",
            "details": [str(video_path)],
        }

    rel_name = str(video_path.relative_to(OUTPUT_ROOT))
    print(
        "worker-comfyui-h3 - Recovered generated video missing from stock "
        f"history output: {rel_name} bytes={len(blob)}"
    )

    payload = {
        "images": [
            {
                "filename": video_path.name,
                "type": "base64",
                "data": base64.b64encode(blob).decode("ascii"),
            }
        ],
        "h3_video_recovered": True,
        "h3_video_path": rel_name,
    }

    # Preserve useful warnings but drop stock success_no_images because media
    # was in fact recovered.
    if isinstance(result, dict):
        errors = result.get("errors")
        if isinstance(errors, list) and errors:
            payload["errors"] = errors

    return payload


if __name__ == "__main__":
    print("worker-comfyui-h3 - Starting H3-aware handler shim...")
    runpod.serverless.start({"handler": handler})
