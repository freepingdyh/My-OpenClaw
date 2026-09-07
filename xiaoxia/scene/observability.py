# -*- coding: utf-8 -*-
"""Photo Scene SSOT observability.

This module changes display/diagnostics only. It does not add a prompt source and
it does not alter Seedream generation semantics.

For ordinary /photo embeds, the field labelled "場景" must show the actual
`authoritative_scene`, because that is the single visual truth used for
responsibility tracing. `scene_summary` remains a short title/index summary.
"""
from __future__ import annotations

_APP = None
_ORIGINAL_BUILD_PHOTO_EMBED = None


def _clean(value):
    app = _APP
    if app is None:
        return str(value or "").strip()
    return app._clean_text_compact(value or "")


def _build_photo_embed_scene_ssot(context, title_prefix="📸 小俠照片", attachment_filename=None):
    original = _ORIGINAL_BUILD_PHOTO_EMBED
    if original is None:
        raise RuntimeError("original _build_photo_embed is not installed")

    embed = original(context, title_prefix=title_prefix, attachment_filename=attachment_filename)
    context = context if isinstance(context, dict) else {}

    photo_type = str(
        context.get("db_type")
        or context.get("type")
        or context.get("source_mode")
        or ""
    ).lower()
    is_photobook = photo_type == "photobook" or str(context.get("album_type") or "").lower() == "photobook"
    is_diary = str(context.get("source_mode") or context.get("type") or "").lower() == "diary"
    is_autonomy = False
    try:
        is_autonomy = bool(_APP._is_autonomy_context(context))
    except Exception:
        pass

    # Diary/autonomy/photobook already have their own intentionally richer display.
    # Ordinary /photo used to show scene_summary (40-char UI summary) under the label
    # "場景", which made it impossible to audit the real scene contract.
    if not is_photobook and not is_diary and not is_autonomy:
        authoritative = _clean(context.get("authoritative_scene"))
        if authoritative:
            try:
                for idx, field in enumerate(embed.fields):
                    if str(getattr(field, "name", "")) == "場景":
                        embed.set_field_at(idx, name="場景", value=authoritative[:1024], inline=False)
                        break
                else:
                    embed.add_field(name="場景", value=authoritative[:1024], inline=False)
            except Exception as exc:
                print(f"⚠️ [PHOTO_SCENE_SSOT_DISPLAY_FAILED] {type(exc).__name__}: {exc}")

    return embed


def install_photo_scene_observability(app):
    global _APP, _ORIGINAL_BUILD_PHOTO_EMBED
    _APP = app

    existing = getattr(app, "_build_photo_embed", None)
    if existing is None:
        raise RuntimeError("_build_photo_embed not found")

    if getattr(existing, "_scene_ssot_display_v11205a", False):
        return {
            "module": "xiaoxia.scene.observability",
            "patched": "_build_photo_embed",
            "display_source": "authoritative_scene",
            "already_installed": True,
        }

    _ORIGINAL_BUILD_PHOTO_EMBED = existing
    _build_photo_embed_scene_ssot._scene_ssot_display_v11205a = True
    _build_photo_embed_scene_ssot._scene_ssot_display_original = existing
    app._V11205A_ORIGINAL_BUILD_PHOTO_EMBED = existing
    app._build_photo_embed = _build_photo_embed_scene_ssot

    return {
        "module": "xiaoxia.scene.observability",
        "patched": "_build_photo_embed",
        "display_source": "authoritative_scene",
        "already_installed": False,
    }
