# -*- coding: utf-8 -*-
"""RunPod Pod lifecycle controller used by Xiaoxia on Zeabur.

This module is intentionally standalone and is NOT installed into
xiaoxia_runtime_flat.py yet.

Environment:
    RUNPOD_API_KEY             RunPod GraphQL Read/Write API key.
    XIAOXIA_RUNPOD_POD_ID      Pod to control.

The current integration uses RunPod GraphQL because the user's scoped key was
created for that API. RunPod has announced GraphQL retirement in early 2027;
this module is deliberately isolated so it can later be replaced by API v2
without changing Discord or media-service code.
"""

from __future__ import annotations

import asyncio
import os
from typing import Any

import aiohttp

_GRAPHQL_URL = "https://api.runpod.io/graphql"


class RunPodControllerError(RuntimeError):
    """RunPod control-plane request failed."""


def _config() -> tuple[str, str]:
    api_key = os.getenv("RUNPOD_API_KEY", "").strip()
    pod_id = os.getenv("XIAOXIA_RUNPOD_POD_ID", "").strip()
    if not api_key:
        raise RunPodControllerError("RUNPOD_API_KEY is not configured")
    if not pod_id:
        raise RunPodControllerError("XIAOXIA_RUNPOD_POD_ID is not configured")
    return api_key, pod_id


async def _graphql(query: str, *, timeout_seconds: float = 20.0) -> dict[str, Any]:
    api_key, _ = _config()
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)

    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.post(
                _GRAPHQL_URL,
                params={"api_key": api_key},
                json={"query": query},
                headers={"content-type": "application/json"},
            ) as response:
                payload = await response.json(content_type=None)
    except Exception as exc:
        raise RunPodControllerError(
            f"RunPod GraphQL request failed: {type(exc).__name__}"
        ) from exc

    if response.status >= 400:
        raise RunPodControllerError(f"RunPod GraphQL HTTP {response.status}")

    errors = payload.get("errors")
    if errors:
        messages = "; ".join(
            str(item.get("message", "GraphQL error"))
            for item in errors
            if isinstance(item, dict)
        ) or "GraphQL error"
        raise RunPodControllerError(messages)

    data = payload.get("data")
    if not isinstance(data, dict):
        raise RunPodControllerError("RunPod GraphQL response has no data")
    return data


async def get_pod_status() -> dict[str, Any]:
    """Return a compact status snapshot for the configured Pod."""
    _, pod_id = _config()
    query = f"""
    query {{
      pod(input: {{ podId: "{pod_id}" }}) {{
        id
        name
        desiredStatus
        runtime {{
          uptimeInSeconds
        }}
      }}
    }}
    """
    data = await _graphql(query)
    pod = data.get("pod")
    if not isinstance(pod, dict):
        raise RunPodControllerError(f"Pod not found: {pod_id}")

    runtime = pod.get("runtime")
    return {
        "id": pod.get("id"),
        "name": pod.get("name"),
        "desired_status": pod.get("desiredStatus"),
        "running": pod.get("desiredStatus") == "RUNNING",
        "runtime_ready": isinstance(runtime, dict),
        "uptime_seconds": (
            runtime.get("uptimeInSeconds") if isinstance(runtime, dict) else None
        ),
    }


async def start_pod(*, gpu_count: int = 1) -> dict[str, Any]:
    """Resume the configured stopped Pod."""
    _, pod_id = _config()
    query = f"""
    mutation {{
      podResume(input: {{ podId: "{pod_id}", gpuCount: {int(gpu_count)} }}) {{
        id
        desiredStatus
        imageName
      }}
    }}
    """
    data = await _graphql(query)
    result = data.get("podResume")
    if not isinstance(result, dict):
        raise RunPodControllerError("podResume returned no Pod")
    return {
        "id": result.get("id"),
        "desired_status": result.get("desiredStatus"),
        "image_name": result.get("imageName"),
    }


async def stop_pod() -> dict[str, Any]:
    """Stop the configured Pod and release its GPU."""
    _, pod_id = _config()
    query = f"""
    mutation {{
      podStop(input: {{ podId: "{pod_id}" }}) {{
        id
        desiredStatus
      }}
    }}
    """
    data = await _graphql(query)
    result = data.get("podStop")
    if not isinstance(result, dict):
        raise RunPodControllerError("podStop returned no Pod")
    return {
        "id": result.get("id"),
        "desired_status": result.get("desiredStatus"),
    }


async def wait_until_running(
    *,
    timeout_seconds: float = 300.0,
    poll_seconds: float = 5.0,
) -> dict[str, Any]:
    """Wait until RunPod reports RUNNING and runtime is available."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout_seconds
    last: dict[str, Any] | None = None

    while loop.time() < deadline:
        last = await get_pod_status()
        if last["running"] and last["runtime_ready"]:
            return last
        await asyncio.sleep(poll_seconds)

    raise RunPodControllerError(
        f"Pod did not become runtime-ready within {timeout_seconds:.0f}s; "
        f"last={last}"
    )
