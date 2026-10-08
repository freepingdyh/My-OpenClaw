# -*- coding: utf-8 -*-
"""Inactive RunPod Serverless client for open-weight MiniMax H3 FL2VA.

This module is intentionally not installed into the production Discord runtime
yet.  It reuses the existing RunPod worker-comfyui request contract but keeps
H3 endpoint selection independent so a cloned test endpoint can be used first.

The bundled workflow follows Comfy-Org's official H3 I2V baseline:
- FL2VA pruned INT8 ConvRot
- Qwen3-VL-32B NVFP4 AWQ
- H3 video/audio VAEs
- res_multistep + simple scheduler
- native 24 fps video + stereo audio

worker-comfyui returns PreviewVideo files through output.images[]; the filename
keeps its .mp4/.webm extension, so the same base64 transport used for Qwen
images can carry the generated video bytes without a custom worker handler.
"""
from __future__ import annotations

import asyncio
import base64
import copy
import json
import os
from pathlib import Path
from typing import Any

import aiohttp

from xiaoxia.media.runpod_serverless import RunPodServerlessError

_RUNPOD_INFERENCE_BASE = "https://api.runpod.ai/v2"
_WORKFLOW_PATH = Path(__file__).resolve().parents[1] / "serverless" / "workflows" / "minimax_h3_fl2va_api.json"
_FIRST_FRAME_NAME = "h3_first_frame.png"

DEFAULT_MODEL = "minimax_h3_fl2va_pruned_int8_convrot.safetensors"
DEFAULT_TEXT_ENCODER = "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors"
DEFAULT_VIDEO_VAE = "minimax_h3_video_vae_int8_convrot.safetensors"
DEFAULT_AUDIO_VAE = "minimax_h3_audio_vae_fp32.safetensors"

_TERMINAL = {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}


def _api_key() -> str:
    value = (
        os.environ.get("XIAOXIA_H3_RUNPOD_API_KEY", "").strip()
        or os.environ.get("XIAOXIA_RUNPOD_SERVERLESS_API_KEY", "").strip()
        or os.environ.get("RUNPOD_API_KEY", "").strip()
    )
    if not value:
        raise RunPodServerlessError("H3 RunPod API key is not configured")
    return value


def _endpoint_id() -> str:
    value = (
        os.environ.get("XIAOXIA_H3_RUNPOD_ENDPOINT_ID", "").strip()
        or os.environ.get("XIAOXIA_RUNPOD_SERVERLESS_ENDPOINT_ID", "").strip()
    )
    if not value:
        raise RunPodServerlessError("H3 RunPod endpoint id is not configured")
    return value


def _single(workflow: dict[str, Any], class_type: str) -> tuple[str, dict[str, Any]]:
    rows = [
        (str(node_id), node)
        for node_id, node in workflow.items()
        if isinstance(node, dict) and node.get("class_type") == class_type
    ]
    if len(rows) != 1:
        raise RunPodServerlessError(
            f"Expected one {class_type} node, found {len(rows)}"
        )
    return rows[0]


def load_h3_workflow() -> dict[str, Any]:
    try:
        workflow = json.loads(_WORKFLOW_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RunPodServerlessError(
            f"Could not read H3 API workflow: {type(exc).__name__}: {exc}"
        ) from exc
    if not isinstance(workflow, dict) or not workflow:
        raise RunPodServerlessError("H3 API workflow is empty or invalid")

    _single(workflow, "LoadImage")
    _single(workflow, "MiniMaxH3ImageToVideo")
    _single(workflow, "UNETLoader")
    _single(workflow, "CLIPLoader")
    vaes = [
        node for node in workflow.values()
        if isinstance(node, dict) and node.get("class_type") == "VAELoader"
    ]
    if len(vaes) != 2:
        raise RunPodServerlessError(f"Expected two H3 VAELoader nodes, found {len(vaes)}")
    _single(workflow, "SamplerCustomAdvanced")
    _single(workflow, "CreateVideo")
    _single(workflow, "SaveVideo")
    return workflow


def duration_to_length(duration_seconds: float) -> int:
    """Match the official ComfyUI H3 template's 24-fps 17k+5 frame grid."""
    frames = max(5, round(float(duration_seconds) * 24.0))
    return int(frames + (5 - (frames % 17)) % 17)


def build_h3_job(
    first_frame_bytes: bytes,
    *,
    prompt: str,
    duration_seconds: float = 5.0,
    width: int = 864,
    height: int = 480,
    steps: int = 20,
    seed: int = 1,
) -> dict[str, Any]:
    if not first_frame_bytes:
        raise RunPodServerlessError("H3 first frame is empty")
    if not str(prompt or "").strip():
        raise RunPodServerlessError("H3 prompt is empty")

    width = max(32, int(width) // 32 * 32)
    height = max(32, int(height) // 32 * 32)
    steps = max(1, int(steps))

    workflow = copy.deepcopy(load_h3_workflow())

    _, image = _single(workflow, "LoadImage")
    image["inputs"]["image"] = _FIRST_FRAME_NAME

    _, h3 = _single(workflow, "MiniMaxH3ImageToVideo")
    h3["inputs"]["prompt"] = str(prompt).strip()
    h3["inputs"]["width"] = width
    h3["inputs"]["height"] = height
    h3["inputs"]["length"] = duration_to_length(duration_seconds)

    _, noise = _single(workflow, "RandomNoise")
    noise["inputs"]["noise_seed"] = int(seed)

    _, scheduler = _single(workflow, "BasicScheduler")
    scheduler["inputs"]["steps"] = steps

    encoded = base64.b64encode(first_frame_bytes).decode("ascii")
    return {
        "input": {
            "workflow": workflow,
            "images": [
                {
                    "name": _FIRST_FRAME_NAME,
                    "image": "data:image/png;base64," + encoded,
                }
            ],
        }
    }


async def _request(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    timeout_seconds: float = 30.0,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Accept": "application/json",
    }
    if json_body is not None:
        headers["Content-Type"] = "application/json"

    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    url = f"{_RUNPOD_INFERENCE_BASE}/{_endpoint_id()}{path}"
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.request(method, url, headers=headers, json=json_body) as resp:
                raw = await resp.text()
                try:
                    payload = json.loads(raw) if raw else {}
                except Exception:
                    payload = {"raw": raw[:3000]}
                if resp.status >= 400:
                    raise RunPodServerlessError(
                        f"H3 RunPod HTTP {resp.status} {method} {path}: {payload}"
                    )
                if not isinstance(payload, dict):
                    raise RunPodServerlessError("H3 RunPod response is not an object")
                return payload
    except RunPodServerlessError:
        raise
    except Exception as exc:
        raise RunPodServerlessError(
            f"H3 RunPod request failed: {type(exc).__name__}: {exc}"
        ) from exc


async def wait_for_h3_job(
    job_id: str,
    *,
    timeout_seconds: float = 1200.0,
    poll_seconds: float = 3.0,
) -> dict[str, Any]:
    loop = asyncio.get_running_loop()
    deadline = loop.time() + float(timeout_seconds)
    last: dict[str, Any] | None = None
    while loop.time() < deadline:
        last = await _request("GET", f"/status/{job_id}", timeout_seconds=30)
        state = str(last.get("status") or "").upper()
        if state in _TERMINAL:
            return last
        await asyncio.sleep(float(poll_seconds))
    raise RunPodServerlessError(
        f"H3 RunPod job timed out after {timeout_seconds:.0f}s; "
        f"job_id={job_id} last_status={(last or {}).get('status')}"
    )


def decode_h3_video(completed_job: dict[str, Any]) -> tuple[str, bytes]:
    state = str(completed_job.get("status") or "").upper()
    if state != "COMPLETED":
        raise RunPodServerlessError(
            f"Cannot decode H3 video from status={state or 'UNKNOWN'}"
        )

    output = completed_job.get("output")
    if not isinstance(output, dict):
        raise RunPodServerlessError("H3 completed job has no output object")
    if output.get("error"):
        raise RunPodServerlessError(f"H3 worker returned error: {output.get('error')}")

    # ComfyUI PreviewVideo intentionally serializes saved video files under
    # the UI key "images"; worker-comfyui therefore returns them in images[].
    items = output.get("images")
    if not isinstance(items, list) or not items:
        raise RunPodServerlessError(f"H3 worker returned no media: {output}")

    for item in items:
        if not isinstance(item, dict):
            continue
        filename = str(item.get("filename") or "").strip()
        result_type = str(item.get("type") or "").strip()
        data = item.get("data")
        if result_type != "base64" or not isinstance(data, str) or not data:
            continue
        if filename.lower().endswith((".mp4", ".webm", ".mkv", ".mov")):
            try:
                blob = base64.b64decode(data, validate=True)
            except Exception as exc:
                raise RunPodServerlessError(
                    f"Invalid base64 H3 video: {filename}"
                ) from exc
            if blob:
                return filename, blob

    raise RunPodServerlessError(
        "H3 worker completed but returned no supported base64 video file"
    )


async def run_h3(
    first_frame_bytes: bytes,
    *,
    prompt: str,
    duration_seconds: float = 5.0,
    width: int = 864,
    height: int = 480,
    steps: int = 20,
    seed: int = 1,
    timeout_seconds: float = 1200.0,
) -> tuple[str, bytes, dict[str, Any]]:
    job = build_h3_job(
        first_frame_bytes,
        prompt=prompt,
        duration_seconds=duration_seconds,
        width=width,
        height=height,
        steps=steps,
        seed=seed,
    )
    submitted = await _request("POST", "/run", json_body=job, timeout_seconds=30)
    job_id = str(submitted.get("id") or "").strip()
    if not job_id:
        raise RunPodServerlessError(f"H3 RunPod submit response has no job id: {submitted}")

    completed = await wait_for_h3_job(
        job_id,
        timeout_seconds=timeout_seconds,
    )
    state = str(completed.get("status") or "").upper()
    if state != "COMPLETED":
        raise RunPodServerlessError(
            f"H3 RunPod job ended status={state or 'UNKNOWN'} "
            f"job_id={job_id} error={completed.get('error')}"
        )
    filename, blob = decode_h3_video(completed)
    meta = {
        "provider": "runpod",
        "backend": "open_weights_comfyui",
        "checkpoint_family": "FL2VA",
        "model": DEFAULT_MODEL,
        "text_encoder": DEFAULT_TEXT_ENCODER,
        "video_vae": DEFAULT_VIDEO_VAE,
        "audio_vae": DEFAULT_AUDIO_VAE,
        "job_id": job_id,
        "duration_seconds": float(duration_seconds),
        "width": int(width),
        "height": int(height),
        "steps": int(steps),
        "seed": int(seed),
        "length_frames": duration_to_length(duration_seconds),
        "filename": filename,
    }
    return filename, blob, meta
