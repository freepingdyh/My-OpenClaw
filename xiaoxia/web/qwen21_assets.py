# -*- coding: utf-8 -*-
"""Protected Qwen Image 2.1 asset routes for RunPod workers.

Serves only an explicit allowlist from Zeabur persistent storage.
No directory browsing and no path passthrough.
"""
from __future__ import annotations

import hmac
import os
from pathlib import Path
from typing import Any, Dict

from fastapi import Header, HTTPException
from fastapi.responses import FileResponse

_ROOT = Path("/data/memory/qwen21")
_REFS = _ROOT / "refs"
_WORKFLOWS = _ROOT / "workflows"
_META = _ROOT / "meta"

_ALLOWED_REFS = {
    "image_2_face_front.png",
    "image_3_face_45.png",
    "image_4_body_full.png",
    "image_5_body_half.png",
    "image_6_body_clothed.png",
    "image_4_body_full_clothed.png",
    "image_5_body_half_clothed.png",
    # qwen2.1_special_v2 reference assets selected through /qwen_lab
    "image_4_body_full_v2.png",
    "image_5_body_half_front_v2.png",
    "image_7_body_half_45_v2.png",
    "image_8_body_half_90_v2.png",
}
_ALLOWED_WORKFLOWS = {
    "xiaoxia_qwen21_special_v1.json",
    "xiaoxia_qwen21_special_v1_api.json",
}


def _require_asset_key(provided: str | None) -> None:
    expected = (os.environ.get("XIAOXIA_ASSET_TOKEN") or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="asset service not configured")
    if not provided or not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="unauthorized")


def _file_response(path: Path, media_type: str) -> FileResponse:
    if not path.is_file():
        raise HTTPException(status_code=404, detail="asset not found")
    return FileResponse(
        path=str(path),
        media_type=media_type,
        filename=path.name,
        headers={"Cache-Control": "no-store"},
    )


def install_qwen21_asset_routes(app: Any) -> Dict[str, Any]:
    if getattr(app, "_xiaoxia_qwen21_asset_routes_installed", False):
        return {"installed": False, "reason": "already_installed"}

    api_app = getattr(app, "api_app", None)
    if api_app is None:
        raise RuntimeError("api_app not found; Qwen21 asset routes cannot be installed")

    @api_app.get("/internal/qwen21/refs/{filename}", include_in_schema=False)
    async def qwen21_ref(
        filename: str,
        x_xiaoxia_asset_key: str | None = Header(
            default=None, alias="X-Xiaoxia-Asset-Key"
        ),
    ):
        _require_asset_key(x_xiaoxia_asset_key)
        if filename not in _ALLOWED_REFS:
            raise HTTPException(status_code=404, detail="asset not found")
        return _file_response(_REFS / filename, "image/png")

    @api_app.get("/internal/qwen21/workflows/{filename}", include_in_schema=False)
    async def qwen21_workflow(
        filename: str,
        x_xiaoxia_asset_key: str | None = Header(
            default=None, alias="X-Xiaoxia-Asset-Key"
        ),
    ):
        _require_asset_key(x_xiaoxia_asset_key)
        if filename not in _ALLOWED_WORKFLOWS:
            raise HTTPException(status_code=404, detail="asset not found")
        return _file_response(_WORKFLOWS / filename, "application/json")

    @api_app.get("/internal/qwen21/meta/sha256.txt", include_in_schema=False)
    async def qwen21_checksums(
        x_xiaoxia_asset_key: str | None = Header(
            default=None, alias="X-Xiaoxia-Asset-Key"
        ),
    ):
        _require_asset_key(x_xiaoxia_asset_key)
        return _file_response(_META / "sha256.txt", "text/plain")

    app._xiaoxia_qwen21_asset_routes_installed = True
    print("🔐 [QWEN21_ASSET_ROUTES] protected_routes=3 root=/data/memory/qwen21")
    return {
        "installed": True,
        "root": str(_ROOT),
        "refs": sorted(_ALLOWED_REFS),
        "workflows": sorted(_ALLOWED_WORKFLOWS),
    }
