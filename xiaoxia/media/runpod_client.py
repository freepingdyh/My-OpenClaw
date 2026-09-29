# -*- coding: utf-8 -*-
"""Zeabur-side client for the authenticated Xiaoxia RunPod media gateway."""

from __future__ import annotations

import os
from typing import Any

import aiohttp


class RunPodGatewayConfigError(RuntimeError):
    pass


def _config() -> tuple[str, str]:
    base_url = os.getenv("XIAOXIA_RUNPOD_GATEWAY_URL", "").strip().rstrip("/")
    api_key = os.getenv("XIAOXIA_RUNPOD_GATEWAY_KEY", "").strip()
    if not base_url:
        raise RunPodGatewayConfigError("XIAOXIA_RUNPOD_GATEWAY_URL is not configured")
    if not api_key:
        raise RunPodGatewayConfigError("XIAOXIA_RUNPOD_GATEWAY_KEY is not configured")
    return base_url, api_key


async def _request(method: str, path: str, *, timeout_seconds: float = 10.0) -> Any:
    base_url, api_key = _config()
    timeout = aiohttp.ClientTimeout(total=timeout_seconds)
    headers = {"Authorization": f"Bearer {api_key}"}
    async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
        async with session.request(method, f"{base_url}{path}") as response:
            data = await response.json(content_type=None)
            if response.status >= 400:
                raise RuntimeError(
                    f"RunPod gateway HTTP {response.status}: {data}"
                )
            return data


async def gateway_health() -> dict[str, Any]:
    return await _request("GET", "/health")


async def comfy_health() -> dict[str, Any]:
    return await _request("GET", "/comfy-health")


async def auth_check() -> dict[str, Any]:
    return await _request("POST", "/auth-check")
