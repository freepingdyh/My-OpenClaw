# -*- coding: utf-8 -*-
"""v1.12.06ae — always submit H3 source images through fal storage.

The H3 provider accepts public image URLs, but an external host adds another fetch layer.
For Xiaoxia we want one deterministic transport path:

    source image -> exact bytes/local file -> fal_client.upload_file -> H3

This module changes transport only. It does not alter the Director plan, prompt, image
content, safety settings, model selection, or audio behavior.
"""
from __future__ import annotations

import asyncio
import mimetypes
import os
import tempfile
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import aiohttp

from xiaoxia.video import h3

_ORIGINAL_ENSURE_IMAGE_URL = None


def _suffix_from_source(source: str, content_type: Optional[str] = None) -> str:
    suffix = os.path.splitext(urlparse(str(source or "")).path)[1].lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".avif"}:
        return suffix
    if content_type:
        guessed = mimetypes.guess_extension(str(content_type).split(";", 1)[0].strip().lower()) or ""
        if guessed == ".jpe":
            guessed = ".jpg"
        if guessed:
            return guessed
    return ".jpg"


async def _download_to_temp(url: str) -> str:
    timeout = aiohttp.ClientTimeout(total=60)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"H3_SOURCE_IMAGE_DOWNLOAD_HTTP_{resp.status}")
            data = await resp.read()
            if not data:
                raise RuntimeError("H3_SOURCE_IMAGE_DOWNLOAD_EMPTY")
            suffix = _suffix_from_source(url, resp.headers.get("Content-Type"))

    fd, path = tempfile.mkstemp(prefix="xiaoxia_h3_source_", suffix=suffix)
    os.close(fd)
    with open(path, "wb") as f:
        f.write(data)
    return path


async def _fal_native_image_url(app: Any, context: Dict[str, Any]) -> str:
    ctx = context or {}

    # Avoid duplicate uploads if the same generation path asks twice.
    cached = str(ctx.get("h3_fal_image_url") or "").strip()
    if cached.startswith(("http://", "https://")):
        return cached

    candidates = h3._image_candidates(ctx)
    local = next((value for value in candidates if os.path.exists(value)), None)
    temp_path = None
    source_kind = "local"

    try:
        if local:
            upload_path = local
        else:
            remote = next(
                (value for value in candidates if value.startswith(("http://", "https://"))),
                None,
            )
            if not remote:
                raise RuntimeError("H3_SOURCE_IMAGE_NOT_FOUND")
            source_kind = "remote_reuploaded"
            temp_path = await _download_to_temp(remote)
            upload_path = temp_path

        fal_client = app._get_fal_client()
        fal_url = await asyncio.to_thread(fal_client.upload_file, upload_path)
        fal_url = str(fal_url or "").strip()
        if not fal_url.startswith(("http://", "https://")):
            raise RuntimeError("H3_FAL_IMAGE_UPLOAD_NO_URL")

        ctx["h3_fal_image_url"] = fal_url
        ctx["h3_image_transport"] = "fal_storage"
        print(f"📤 [H3_FAL_NATIVE_IMAGE] source={source_kind} transport=fal_storage")
        return fal_url
    finally:
        if temp_path:
            try:
                os.remove(temp_path)
            except Exception:
                pass


def install_fal_native_image_transport(app: Any) -> Dict[str, Any]:
    global _ORIGINAL_ENSURE_IMAGE_URL
    if getattr(h3, "_xiaoxia_fal_native_image_transport_installed", False):
        return {"patched": False, "reason": "already_installed"}

    _ORIGINAL_ENSURE_IMAGE_URL = h3._ensure_image_url
    h3._ensure_image_url = _fal_native_image_url
    h3._xiaoxia_fal_native_image_transport_installed = True

    return {
        "patched": True,
        "transport": "fal_storage_first",
        "remote_source": "download_exact_bytes_then_upload_file",
        "local_source": "upload_file",
        "prompt_unchanged": True,
        "director_unchanged": True,
        "provider_safety_unchanged": True,
    }
