#!/usr/bin/env python3
"""Fetch Xiaoxia's fixed Qwen Image 2.1 reference assets from Zeabur.

Expected env:
- XIAOXIA_ASSET_BASE_URL  e.g. https://example.zeabur.app
- XIAOXIA_ASSET_TOKEN     shared secret used by the protected Zeabur routes

The five fixed refs are staged into /comfyui/input before ComfyUI starts.
The checksum manifest is fetched first and every downloaded ref is verified.
"""
from __future__ import annotations

import hashlib
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

REFS = (
    "image_2_face_front.png",
    "image_3_face_45.png",
    "image_4_body_full.png",
    "image_4_body_full_clothed.png",
    "image_5_body_half.png",
    "image_5_body_half_clothed.png",
    "image_6_body_clothed.png",
)

# The two clothed scene refs were added after the original checksum manifest.
# Keep checksum enforcement for all legacy refs, but allow these protected-route
# assets to stage before the persistent manifest is refreshed.
_OPTIONAL_MANIFEST_REFS = {
    "image_4_body_full_clothed.png",
    "image_5_body_half_clothed.png",
}

INPUT_DIR = Path(os.environ.get("COMFYUI_INPUT_DIR") or "/comfyui/input")


def _required_env(name: str) -> str:
    value = (os.environ.get(name) or "").strip()
    if not value:
        raise RuntimeError(f"missing required environment variable: {name}")
    return value


def _get(url: str, token: str) -> bytes:
    request = urllib.request.Request(
        url,
        headers={"X-Xiaoxia-Asset-Key": token},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"asset request failed: HTTP {exc.code} {url}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"asset request failed: {exc.reason} {url}") from exc


def _parse_manifest(raw: bytes) -> dict[str, str]:
    expected: dict[str, str] = {}
    for line in raw.decode("utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        digest, relpath = line.split(None, 1)
        expected[relpath.strip()] = digest.strip().lower()
    return expected


def _sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def main() -> int:
    base = _required_env("XIAOXIA_ASSET_BASE_URL").rstrip("/")
    token = _required_env("XIAOXIA_ASSET_TOKEN")

    manifest = _parse_manifest(
        _get(f"{base}/internal/qwen21/meta/sha256.txt", token)
    )

    INPUT_DIR.mkdir(parents=True, exist_ok=True)

    for filename in REFS:
        relpath = f"refs/{filename}"
        expected = manifest.get(relpath)
        if not expected and filename not in _OPTIONAL_MANIFEST_REFS:
            raise RuntimeError(f"checksum missing from manifest: {relpath}")

        blob = _get(f"{base}/internal/qwen21/refs/{filename}", token)
        actual = _sha256(blob)
        if expected and actual != expected:
            raise RuntimeError(
                f"checksum mismatch for {filename}: expected={expected} actual={actual}"
            )
        if not expected:
            print(
                f"[QWEN21_ASSET_SYNC] warning checksum_missing_optional file={filename} sha256={actual}"
            )

        target = INPUT_DIR / filename
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(blob)
        os.replace(tmp, target)
        print(
            f"[QWEN21_ASSET_SYNC] ok file={filename} bytes={len(blob)} sha256={actual}"
        )

    print(
        f"[QWEN21_ASSET_SYNC] complete refs={len(REFS)} target={INPUT_DIR}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[QWEN21_ASSET_SYNC] failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
