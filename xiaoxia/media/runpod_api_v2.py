# -*- coding: utf-8 -*-
"""RunPod REST API v2 client for Xiaoxia infrastructure automation.

API v2 is currently public beta. This module is isolated from Discord/runtime
code so endpoint changes can be absorbed here without changing Xiaoxia product
behavior.

Environment:
    RUNPOD_API_KEY
"""

from __future__ import annotations

import os
from typing import Any

import aiohttp

# The live OpenAPI document declares https://api.runpod.io as its server and
# exposes paths beginning with /v2. Keep the host and path prefix separate to
# avoid accidentally calling /v2/v2/....
_BASE_URL = "https://api.runpod.io"


class RunPodV2Error(RuntimeError):
    pass


def _api_key() -> str:
    key = os.getenv("RUNPOD_API_KEY", "").strip()
    if not key:
        raise RunPodV2Error("RUNPOD_API_KEY is not configured")
    return key


async def _request(
    method: str,
    path: str,
    *,
    json_body: dict[str, Any] | None = None,
    timeout_seconds: float = 30.0,
) -> Any:
    url = f"{_BASE_URL}{path}"
    headers = {
        "Authorization": f"Bearer {_api_key()}",
        "Accept": "application/json",
    }
    if json_body is not None:
        headers["Content-Type"] = "application/json"

    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
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
                    payload = await response.json(content_type=None)
                except Exception:
                    payload = {"raw": text[:2000]}

                if response.status >= 400:
                    raise RunPodV2Error(
                        f"RunPod API v2 HTTP {response.status} "
                        f"{method} {path}: {payload}"
                    )
                return payload
    except RunPodV2Error:
        raise
    except Exception as exc:
        raise RunPodV2Error(
            f"RunPod API v2 request failed for {method} {path}: "
            f"{type(exc).__name__}: {exc}"
        ) from exc


async def fetch_openapi() -> dict[str, Any]:
    payload = await _request("GET", "/v2/openapi.json")
    if not isinstance(payload, dict):
        raise RunPodV2Error("OpenAPI response is not an object")
    return payload


async def get_pod(pod_id: str) -> dict[str, Any]:
    payload = await _request("GET", f"/v2/pods/{pod_id}")
    if not isinstance(payload, dict):
        raise RunPodV2Error("Pod response is not an object")
    return payload


async def pod_action(pod_id: str, action: str) -> dict[str, Any]:
    payload = await _request(
        "POST",
        f"/v2/pods/{pod_id}/action",
        json_body={"action": action},
    )
    if not isinstance(payload, dict):
        raise RunPodV2Error("Pod action response is not an object")
    return payload


async def list_gpu_types() -> dict[str, Any]:
    payload = await _request("GET", "/v2/catalog/gpus")
    if not isinstance(payload, dict):
        raise RunPodV2Error("GPU catalog response is not an object")
    return payload


async def get_gpu_type(gpu_id: str) -> dict[str, Any]:
    payload = await _request("GET", f"/v2/catalog/gpus/{gpu_id}")
    if not isinstance(payload, dict):
        raise RunPodV2Error("GPU catalog response is not an object")
    return payload


async def discover_relevant_operations() -> dict[str, list[dict[str, str]]]:
    spec = await fetch_openapi()
    paths = spec.get("paths")
    if not isinstance(paths, dict):
        raise RunPodV2Error("OpenAPI document has no paths object")

    groups: dict[str, list[dict[str, str]]] = {
        "pods": [],
        "storage": [],
        "hardware": [],
        "templates": [],
    }

    keywords = {
        "pods": ("pod",),
        "storage": ("volume", "storage"),
        "hardware": ("gpu", "hardware", "accelerator"),
        "templates": ("template",),
    }

    for path, operations in paths.items():
        if not isinstance(path, str) or not isinstance(operations, dict):
            continue
        lower_path = path.lower()
        for group, needles in keywords.items():
            if not any(needle in lower_path for needle in needles):
                continue
            for method, operation in operations.items():
                if method.upper() not in {
                    "GET", "POST", "PUT", "PATCH", "DELETE"
                }:
                    continue
                meta = operation if isinstance(operation, dict) else {}
                groups[group].append(
                    {
                        "method": method.upper(),
                        "path": path,
                        "operation_id": str(meta.get("operationId") or ""),
                        "summary": str(meta.get("summary") or ""),
                    }
                )

    for items in groups.values():
        items.sort(key=lambda x: (x["path"], x["method"]))
    return groups


async def probe() -> dict[str, Any]:
    spec = await fetch_openapi()
    info = spec.get("info") if isinstance(spec.get("info"), dict) else {}
    paths = spec.get("paths") if isinstance(spec.get("paths"), dict) else {}
    servers = spec.get("servers") if isinstance(spec.get("servers"), list) else []
    return {
        "ok": True,
        "title": info.get("title"),
        "version": info.get("version"),
        "path_count": len(paths),
        "server": servers[0].get("url") if servers and isinstance(servers[0], dict) else None,
    }


async def get_create_pod_schema() -> dict[str, Any]:
    """Return the fully expanded CreatePodRequest schema from live OpenAPI."""
    spec = await fetch_openapi()
    schemas = (
        spec.get("components", {}).get("schemas", {})
        if isinstance(spec.get("components"), dict)
        else {}
    )
    schema = schemas.get("CreatePodRequest")
    if not isinstance(schema, dict):
        raise RunPodV2Error("CreatePodRequest schema not found")
    return schema
