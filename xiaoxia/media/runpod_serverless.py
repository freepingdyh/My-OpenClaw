# -*- coding: utf-8 -*-
"""RunPod Serverless client for Xiaoxia Qwen Image 2.1.

This module is intentionally standalone and is NOT installed into
xiaoxia_runtime_flat.py yet.

The API-format ComfyUI workflow is owned by Zeabur persistent storage:
    /data/memory/qwen21/workflows/xiaoxia_qwen21_special_v1_api.json

Per request, only image_1 is uploaded dynamically. Fixed image_2-image_6
are staged into /comfyui/input by the worker cold-start asset sync.
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

_RUNPOD_INFERENCE_BASE = "https://api.runpod.ai/v2"
_WORKFLOW_PATH = Path(
    os.environ.get("XIAOXIA_QWEN21_API_WORKFLOW")
    or "/data/memory/qwen21/workflows/xiaoxia_qwen21_special_v1_api.json"
)
_DYNAMIC_IMAGE_NAME = "image_1.png"

_FIXED_REFS = {
    "image_2_face_front.png",
    "image_3_face_45.png",
    "image_4_body_full.png",
    "image_5_body_half.png",
    "image_6_body_clothed.png",
}


class RunPodServerlessError(RuntimeError):
    pass


def _api_key() -> str:
    key = (
        os.environ.get("XIAOXIA_RUNPOD_SERVERLESS_API_KEY", "").strip()
        or os.environ.get("RUNPOD_API_KEY", "").strip()
    )
    if not key:
        raise RunPodServerlessError(
            "XIAOXIA_RUNPOD_SERVERLESS_API_KEY is not configured"
        )
    return key


def _endpoint_id() -> str:
    endpoint_id = os.environ.get("XIAOXIA_RUNPOD_SERVERLESS_ENDPOINT_ID", "").strip()
    if not endpoint_id:
        raise RunPodServerlessError(
            "XIAOXIA_RUNPOD_SERVERLESS_ENDPOINT_ID is not configured"
        )
    return endpoint_id


def load_qwen21_workflow() -> dict[str, Any]:
    if not _WORKFLOW_PATH.is_file():
        raise RunPodServerlessError(
            f"Qwen21 API workflow not found: {_WORKFLOW_PATH}"
        )
    try:
        workflow = json.loads(_WORKFLOW_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        raise RunPodServerlessError(
            f"Could not read Qwen21 API workflow: {type(exc).__name__}: {exc}"
        ) from exc

    if not isinstance(workflow, dict) or not workflow:
        raise RunPodServerlessError("Qwen21 API workflow is empty or invalid")
    _validate_workflow_contract(workflow)
    return workflow


def _nodes_of_type(workflow: dict[str, Any], class_type: str) -> list[tuple[str, dict[str, Any]]]:
    result: list[tuple[str, dict[str, Any]]] = []
    for node_id, node in workflow.items():
        if isinstance(node, dict) and node.get("class_type") == class_type:
            result.append((str(node_id), node))
    return result


def _single_node(workflow: dict[str, Any], class_type: str) -> tuple[str, dict[str, Any]]:
    matches = _nodes_of_type(workflow, class_type)
    if len(matches) != 1:
        raise RunPodServerlessError(
            f"Expected exactly one {class_type} node, found {len(matches)}"
        )
    return matches[0]


def _validate_workflow_contract(workflow: dict[str, Any]) -> None:
    load_nodes = _nodes_of_type(workflow, "LoadImage")
    filenames = {
        str((node.get("inputs") or {}).get("image") or "")
        for _, node in load_nodes
    }

    required = {_DYNAMIC_IMAGE_NAME, *_FIXED_REFS}
    missing = sorted(required - filenames)
    if missing:
        raise RunPodServerlessError(
            "Qwen21 API workflow is missing required LoadImage inputs: "
            + ", ".join(missing)
        )

    _single_node(workflow, "TextEncodeQwenImage21")
    _single_node(workflow, "QwenImage21Cache")
    _single_node(workflow, "KSampler")
    _single_node(workflow, "SaveImageAdvanced")


def build_qwen21_job(
    image_bytes: bytes,
    *,
    prompt: str | None = None,
    negative_prompt: str | None = None,
    seed: int | None = None,
    steps: int | None = None,
    workflow_image_replacements: dict[str, str] | None = None,
    extra_images: dict[str, bytes] | None = None,
) -> dict[str, Any]:
    if not image_bytes:
        raise RunPodServerlessError("image_1 is empty")

    workflow = copy.deepcopy(load_qwen21_workflow())

    if workflow_image_replacements:
        pending = dict(workflow_image_replacements)
        for _, node in _nodes_of_type(workflow, "LoadImage"):
            inputs = node.get("inputs") or {}
            current_name = str(inputs.get("image") or "")
            if current_name in pending:
                inputs["image"] = str(pending.pop(current_name))
        if pending:
            raise RunPodServerlessError(
                "Qwen21 workflow image replacement target not found: "
                + ", ".join(sorted(pending))
            )

    _, encoder = _single_node(workflow, "TextEncodeQwenImage21")
    encoder_inputs = encoder.get("inputs")
    if not isinstance(encoder_inputs, dict):
        raise RunPodServerlessError("TextEncodeQwenImage21 inputs are invalid")

    if prompt is not None:
        encoder_inputs["prompt"] = str(prompt)
    if negative_prompt is not None:
        encoder_inputs["negative_prompt"] = str(negative_prompt)

    if seed is not None or steps is not None:
        _, sampler = _single_node(workflow, "KSampler")
        sampler_inputs = sampler.get("inputs")
        if not isinstance(sampler_inputs, dict):
            raise RunPodServerlessError("KSampler inputs are invalid")
        if seed is not None:
            sampler_inputs["seed"] = int(seed)
        if steps is not None:
            sampler_inputs["steps"] = int(steps)

    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    images = [
        {
            "name": _DYNAMIC_IMAGE_NAME,
            "image": f"data:image/png;base64,{image_b64}",
        }
    ]
    for name, blob in (extra_images or {}).items():
        clean_name = str(name or "").strip()
        if not clean_name or clean_name == _DYNAMIC_IMAGE_NAME:
            raise RunPodServerlessError(f"Invalid extra image name: {clean_name!r}")
        if not blob:
            raise RunPodServerlessError(f"Extra image is empty: {clean_name}")
        images.append(
            {
                "name": clean_name,
                "image": "data:image/png;base64,"
                + base64.b64encode(blob).decode("ascii"),
            }
        )

    return {
        "input": {
            "workflow": workflow,
            "images": images,
        }
    }


def build_qwen21_job_from_path(
    image_path: str | os.PathLike[str],
    *,
    prompt: str | None = None,
    negative_prompt: str | None = None,
    seed: int | None = None,
) -> dict[str, Any]:
    path = Path(image_path)
    if not path.is_file():
        raise RunPodServerlessError(f"image_1 file not found: {path}")
    return build_qwen21_job(
        path.read_bytes(),
        prompt=prompt,
        negative_prompt=negative_prompt,
        seed=seed,
    )


def payload_size_bytes(payload: dict[str, Any]) -> int:
    return len(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    )


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
            async with session.request(
                method,
                url,
                headers=headers,
                json=json_body,
            ) as response:
                text = await response.text()
                try:
                    payload = json.loads(text) if text else {}
                except Exception:
                    payload = {"raw": text[:2000]}

                if response.status >= 400:
                    raise RunPodServerlessError(
                        f"RunPod Serverless HTTP {response.status} "
                        f"{method} {path}: {payload}"
                    )
                if not isinstance(payload, dict):
                    raise RunPodServerlessError(
                        "RunPod Serverless response is not an object"
                    )
                return payload
    except RunPodServerlessError:
        raise
    except Exception as exc:
        raise RunPodServerlessError(
            f"RunPod Serverless request failed: {type(exc).__name__}: {exc}"
        ) from exc


async def submit_qwen21(
    image_bytes: bytes,
    *,
    prompt: str | None = None,
    negative_prompt: str | None = None,
    seed: int | None = None,
    steps: int | None = None,
    workflow_image_replacements: dict[str, str] | None = None,
    extra_images: dict[str, bytes] | None = None,
) -> dict[str, Any]:
    job = build_qwen21_job(
        image_bytes,
        prompt=prompt,
        negative_prompt=negative_prompt,
        seed=seed,
        steps=steps,
        workflow_image_replacements=workflow_image_replacements,
        extra_images=extra_images,
    )
    return await _request("POST", "/run", json_body=job, timeout_seconds=30.0)


async def get_job_status(job_id: str) -> dict[str, Any]:
    job_id = str(job_id).strip()
    if not job_id:
        raise RunPodServerlessError("job_id is required")
    return await _request("GET", f"/status/{job_id}", timeout_seconds=30.0)

_TERMINAL_JOB_STATES = {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}


async def wait_for_job(
    job_id: str,
    *,
    timeout_seconds: float = 600.0,
    poll_seconds: float = 2.0,
) -> dict[str, Any]:
    """Poll a RunPod Serverless job until it reaches a terminal state."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + float(timeout_seconds)
    last: dict[str, Any] | None = None

    while loop.time() < deadline:
        last = await get_job_status(job_id)
        state = str(last.get("status") or "").upper()
        if state in _TERMINAL_JOB_STATES:
            return last
        await asyncio.sleep(float(poll_seconds))

    raise RunPodServerlessError(
        f"RunPod job did not finish within {timeout_seconds:.0f}s; "
        f"job_id={job_id} last_status={(last or {}).get('status')}"
    )


def decode_qwen21_output_images(
    completed_job: dict[str, Any],
) -> list[tuple[str, bytes]]:
    """Decode image bytes from the official worker-comfyui response format.

    worker-comfyui returns:
        output.images[] = {
            "filename": "...",
            "type": "base64",
            "data": "<base64>"
        }

    S3 URL output is intentionally rejected here because Xiaoxia's current
    endpoint does not configure BUCKET_ENDPOINT_URL.
    """
    state = str(completed_job.get("status") or "").upper()
    if state != "COMPLETED":
        raise RunPodServerlessError(
            f"Cannot decode images from non-completed job: status={state or 'UNKNOWN'}"
        )

    output = completed_job.get("output")
    if not isinstance(output, dict):
        raise RunPodServerlessError("Completed RunPod job has no output object")

    top_error = output.get("error")
    if top_error:
        raise RunPodServerlessError(f"RunPod worker returned error: {top_error}")

    images = output.get("images")
    if not isinstance(images, list) or not images:
        raise RunPodServerlessError("Completed RunPod job returned no images")

    decoded: list[tuple[str, bytes]] = []
    for index, item in enumerate(images, start=1):
        if not isinstance(item, dict):
            raise RunPodServerlessError(
                f"Unexpected image result at index {index}: {type(item).__name__}"
            )

        filename = str(item.get("filename") or f"qwen21_{index}.png")
        result_type = str(item.get("type") or "")
        data = item.get("data")

        if result_type != "base64":
            raise RunPodServerlessError(
                f"Unsupported RunPod image result type: {result_type or 'missing'}"
            )
        if not isinstance(data, str) or not data:
            raise RunPodServerlessError(
                f"RunPod image result has no base64 data: {filename}"
            )

        try:
            blob = base64.b64decode(data, validate=True)
        except Exception as exc:
            raise RunPodServerlessError(
                f"Invalid base64 image returned by RunPod: {filename}"
            ) from exc

        if not blob:
            raise RunPodServerlessError(
                f"RunPod returned an empty image: {filename}"
            )
        decoded.append((filename, blob))

    return decoded


async def run_qwen21(
    image_bytes: bytes,
    *,
    prompt: str | None = None,
    negative_prompt: str | None = None,
    seed: int | None = None,
    steps: int | None = None,
    workflow_image_replacements: dict[str, str] | None = None,
    extra_images: dict[str, bytes] | None = None,
    timeout_seconds: float = 600.0,
    poll_seconds: float = 2.0,
) -> list[tuple[str, bytes]]:
    """Submit one Qwen21 job, wait for completion, and return decoded images."""
    submitted = await submit_qwen21(
        image_bytes,
        prompt=prompt,
        negative_prompt=negative_prompt,
        seed=seed,
        workflow_image_replacements=workflow_image_replacements,
        extra_images=extra_images,
    )
    job_id = str(submitted.get("id") or "").strip()
    if not job_id:
        raise RunPodServerlessError(
            f"RunPod submit response has no job id: {submitted}"
        )

    completed = await wait_for_job(
        job_id,
        timeout_seconds=timeout_seconds,
        poll_seconds=poll_seconds,
    )

    state = str(completed.get("status") or "").upper()
    if state != "COMPLETED":
        raise RunPodServerlessError(
            f"RunPod job ended with status={state or 'UNKNOWN'} "
            f"job_id={job_id} error={completed.get('error')}"
        )

    return decode_qwen21_output_images(completed)

