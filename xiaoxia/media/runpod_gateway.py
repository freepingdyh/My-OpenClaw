# -*- coding: utf-8 -*-
"""Authenticated Xiaoxia media gateway for a RunPod Pod.

This module is intentionally standalone. It does not alter Discord command
behavior and is not installed from xiaoxia_runtime_flat.py.

Environment:
    XIAOXIA_MEDIA_GATEWAY_KEY   Required bearer token.
    COMFYUI_BASE_URL            Defaults to http://127.0.0.1:8188.

Run on the RunPod side:
    uvicorn xiaoxia.media.runpod_gateway:app --host 0.0.0.0 --port 8190
"""

from __future__ import annotations

import hmac
import os
from typing import Any

import aiohttp
from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

app = FastAPI(
    title="Xiaoxia RunPod Media Gateway",
    version="0.1.0",
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)

_bearer = HTTPBearer(auto_error=False)


def _expected_key() -> str:
    key = os.getenv("XIAOXIA_MEDIA_GATEWAY_KEY", "").strip()
    if not key:
        raise RuntimeError("XIAOXIA_MEDIA_GATEWAY_KEY is not configured")
    return key


def _comfyui_base_url() -> str:
    return os.getenv("COMFYUI_BASE_URL", "http://127.0.0.1:8188").rstrip("/")


async def require_gateway_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    expected = _expected_key()
    if not hmac.compare_digest(credentials.credentials, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


@app.get("/health", dependencies=[Depends(require_gateway_auth)])
async def health() -> dict[str, str]:
    """Authenticated gateway liveness check."""
    return {"status": "ok", "service": "xiaoxia-media-gateway"}


@app.get("/comfy-health", dependencies=[Depends(require_gateway_auth)])
async def comfy_health() -> dict[str, Any]:
    """Verify that the local ComfyUI process is reachable."""
    url = f"{_comfyui_base_url()}/system_stats"
    timeout = aiohttp.ClientTimeout(total=5)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url) as response:
                body = await response.text()
                if response.status >= 400:
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail=f"ComfyUI returned HTTP {response.status}",
                    )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"ComfyUI unavailable: {type(exc).__name__}",
        ) from exc

    return {
        "status": "ok",
        "service": "comfyui",
        "http_status": 200,
        "response_received": bool(body),
    }


@app.post("/auth-check", dependencies=[Depends(require_gateway_auth)])
async def auth_check() -> dict[str, bool]:
    """Cheap authenticated request used to test Zeabur -> RunPod connectivity."""
    return {"authenticated": True}
