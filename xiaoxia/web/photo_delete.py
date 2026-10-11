# -*- coding: utf-8 -*-
"""Cloud Villa photo deletion by stable photo id.

Restores the web delete control without changing photo generation behavior.
Deletion removes the selected photo DB record and, when it belongs to the gallery
output directory, its local image file.
"""
from __future__ import annotations

import asyncio
import hmac
import os
from typing import Any, Dict

from fastapi import HTTPException, Request
from fastapi.responses import JSONResponse

_HEADER = "x-xiaoxia-vault-key"


def _vault_key() -> str:
    return str(os.environ.get("XIAOXIA_VAULT_PASSWORD") or "xiaoxia520")


def _authorized(request: Request) -> bool:
    supplied = str(request.headers.get(_HEADER) or "")
    return bool(supplied) and hmac.compare_digest(supplied, _vault_key())


def _find_fastapi_app(app: Any):
    web = getattr(app, "api_app", None)
    if web is not None:
        return web
    try:
        from xiaoxia.video import archive
        return archive._find_fastapi_app(app)
    except Exception:
        return None


def _safe_local_photo_path(app: Any, record: Dict[str, Any]) -> str:
    resolver = getattr(app, "_photo_local_path_from_context", None)
    if callable(resolver):
        try:
            path = str(resolver(record) or "")
            if path:
                return path
        except Exception:
            pass

    output_dir = os.path.abspath(str(getattr(app, "OUTPUT_DIR", "") or ""))
    if not output_dir:
        return ""
    for key in ("local_path", "local_filename", "local_url", "image_url"):
        raw = str(record.get(key) or "").strip()
        if not raw:
            continue
        if key == "local_path":
            candidate = os.path.abspath(raw)
        elif key == "local_filename":
            candidate = os.path.abspath(os.path.join(output_dir, os.path.basename(raw)))
        elif "/gallery/" in raw:
            filename = os.path.basename(raw.split("/gallery/", 1)[1].split("?", 1)[0].split("#", 1)[0])
            candidate = os.path.abspath(os.path.join(output_dir, filename))
        else:
            continue
        if candidate == output_dir or candidate.startswith(output_dir + os.sep):
            return candidate
    return ""


def install_photo_delete(app: Any) -> Dict[str, Any]:
    if getattr(app, "_xiaoxia_cloud_villa_photo_delete_installed", False):
        return {"patched": False, "reason": "already_installed"}

    web = _find_fastapi_app(app)
    if web is None:
        raise RuntimeError("FastAPI app not found")

    @web.middleware("http")
    async def protect_photo_delete(request: Request, call_next):
        if request.method == "DELETE" and request.url.path.startswith("/api/photos/"):
            if not _authorized(request):
                return JSONResponse({"detail": "vault authentication required"}, status_code=401)
        return await call_next(request)

    async def delete_photo(photo_id: str):
        rows = await asyncio.to_thread(app.load_memory)
        record = next((r for r in rows if str((r or {}).get("id") or "") == str(photo_id)), None)
        if record is None:
            raise HTTPException(status_code=404, detail="photo not found")

        remaining = [r for r in rows if str((r or {}).get("id") or "") != str(photo_id)]
        await asyncio.to_thread(app.save_memory, remaining)

        path = _safe_local_photo_path(app, record)
        file_deleted = False
        if path and os.path.isfile(path):
            try:
                await asyncio.to_thread(os.remove, path)
                file_deleted = True
            except Exception as exc:
                print(f"⚠️ [CLOUD_VILLA_PHOTO_DELETE_FILE_WARN] {type(exc).__name__}: {exc}")

        print(f"🗑️ [CLOUD_VILLA_PHOTO_DELETED] id={photo_id} file_deleted={file_deleted}")
        return {"deleted": True, "photo_id": photo_id, "file_deleted": file_deleted}

    route_path = "/api/photos/{photo_id}"
    if not any(getattr(r, "path", None) == route_path and "DELETE" in (getattr(r, "methods", set()) or set()) for r in web.routes):
        web.add_api_route(route_path, delete_photo, methods=["DELETE"], name="xiaoxia_delete_photo")

    app._xiaoxia_cloud_villa_photo_delete_installed = True
    return {"patched": True, "delete_api": route_path, "auth_required": True}
