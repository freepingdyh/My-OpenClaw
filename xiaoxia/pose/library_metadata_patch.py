# -*- coding: utf-8 -*-
"""Pose Library v1.13.02 metadata durability patch.

Command semantics are deliberately strict:
- /姿勢 看 is read-only and never mutates library metadata.
- /姿勢 修正 Pxxx 重新判讀 is the explicit operation that reruns Gemini.
- /姿勢 新增 may retry analysis from the stored image only when initial ingestion
  produced blank metadata, because that is still part of the add transaction.

No pose conversion or person replacement is performed here.
"""
from __future__ import annotations

import os
from datetime import datetime
from typing import Any, Dict

from xiaoxia.pose import core

VERSION = "1.13.02"
_PLACEHOLDER_NAMES = {"", "姿勢", "圖片姿勢", "其他"}


def _metadata_missing(row: Dict[str, Any]) -> bool:
    return not any(
        str(row.get(key) or "").strip()
        for key in ("camera_intent", "visible_pose_scope", "pose_description")
    )


def _persist_row(updated: Dict[str, Any]) -> None:
    wanted = str(updated.get("id") or "").strip().upper()
    rows = core._load_index()
    for idx, row in enumerate(rows):
        if str(row.get("id") or "").strip().upper() == wanted:
            rows[idx] = dict(updated)
            core._save_index(rows)
            return


async def refresh_from_stored_image(app: Any, row: Dict[str, Any]) -> Dict[str, Any]:
    """Explicit metadata refresh primitive used by repair flows.

    This function does not run merely because an item is viewed.
    """
    path = str(row.get("file_path") or "").strip()
    if not path or not os.path.exists(path):
        return row

    mime = str(row.get("mime_type") or "image/jpeg").strip() or "image/jpeg"
    try:
        public_url = await app._seedream_upload_single_file(path)
        analysis = await core._analyze(app, public_url, mime)
    except Exception as exc:
        print(f"⚠️ [POSE_LIBRARY_METADATA_UPLOAD_FAILED] {type(exc).__name__}: {exc}")
        return row

    camera = str(analysis.get("camera_intent") or "").strip()
    scope = str(analysis.get("visible_pose_scope") or "").strip()
    desc = str(analysis.get("pose_description") or "").strip()
    if not any((camera, scope, desc)):
        print(f"⚠️ [POSE_LIBRARY_METADATA_EMPTY] id={row.get('id')}")
        return row

    updated = dict(row)
    updated["camera_intent"] = camera
    updated["visible_pose_scope"] = scope
    updated["pose_description"] = desc
    category = core._category_from_analysis(scope, desc)
    updated["category"] = category
    updated["tags"] = core._tags_from_analysis(category, camera, scope, desc)

    old_name = str(updated.get("name") or "").strip()
    if old_name in _PLACEHOLDER_NAMES:
        updated["name"] = core._name_from_analysis(category, camera, desc)

    # Old Pxxx entries may have been produced by the pre-v1.13 experiment. Keep
    # them usable without falsely relabeling them as original-reference assets.
    if str(updated.get("source") or "").strip() != "original_reference":
        updated["source"] = "legacy_pose_asset"

    updated["mime_type"] = mime
    updated["metadata_version"] = VERSION
    updated["updated_at"] = datetime.now().astimezone().isoformat()
    _persist_row(updated)
    print(f"✅ [POSE_LIBRARY_METADATA_REFRESHED] id={updated.get('id')} category={category}")
    return updated


def install_pose_library_metadata_patch(app: Any) -> Dict[str, Any]:
    original_add = core._add_pose

    async def add_with_durable_analysis(app_arg, attachment, note=""):
        row = await original_add(app_arg, attachment, note)
        if _metadata_missing(row):
            row = await refresh_from_stored_image(app, row)
        return row

    # Only ingestion is patched. _show_pose remains untouched/read-only.
    core._add_pose = add_with_durable_analysis
    core.POSE_VERSION = VERSION
    app.refresh_pose_library_metadata = lambda row: refresh_from_stored_image(app, row)

    return {
        "version": VERSION,
        "new_ingest_fallback": "stored-image upload -> Gemini observer",
        "view_semantics": "read-only",
        "repair_semantics": "/姿勢 修正 ...",
        "pose_conversion": False,
    }
