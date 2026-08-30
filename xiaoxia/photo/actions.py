# -*- coding: utf-8 -*-
"""PhotoResultView routing and callback ownership for v1.12.02b.

The stable View class still defines layout/state synchronization. Every user-facing
PhotoResultView button callback is rewired to xiaoxia.photo.handlers, so runtime
business logic no longer executes the legacy callback methods in lobster_discord.py.
"""
from __future__ import annotations

from typing import Any, Dict

from .handlers import HANDLERS

EXTRACTION_VERSION = "1.12.02b"

PHOTO_ACTION_KEYS = {
    "More": "more",
    "🎲 骰子取代": "dice_reroll",
    "🔄 重擲": "full_reroll",
    "💋 魅的幻想": "allure_fantasy",
    "💋 只給大俠": "allure_fantasy",
    "✨ v5.0 場景升級": "v5_refine",
    "🪟 查看 v5 背景": "inspect_v5_background",
    "👗 查看 Nano 服裝": "inspect_clothing_reference",
    "✅ 採用升級版": "adopt_v5",
    "🩹 修正這張": "repair",
    "收藏到衣櫃": "save_wardrobe",
    "上傳成為 Project": "upload_project",
    "上傳成為 Diary": "upload_diary",
}


def photo_action_key(label: str) -> str:
    return PHOTO_ACTION_KEYS.get(str(label or "").strip(), "unknown")


def _wire_external_handlers(view: Any, app: Any) -> Dict[str, Any]:
    wired = []
    missing = []
    for child in list(getattr(view, "children", []) or []):
        label = str(getattr(child, "label", "") or "").strip()
        action_key = PHOTO_ACTION_KEYS.get(label)
        if not action_key:
            continue
        handler = HANDLERS.get(action_key)
        if handler is None:
            missing.append(action_key)
            continue
        if getattr(child, "_xiaoxia_external_handler", False):
            continue

        async def external_callback(interaction, _handler=handler, _action=action_key):
            print(f"📷 [PHOTO_ACTION_ENTER] version={EXTRACTION_VERSION} action={_action} owner=xiaoxia.photo.handlers")
            try:
                return await _handler(view, interaction, app)
            except Exception as exc:
                print(
                    f"❌ [PHOTO_ACTION_UNCAUGHT] version={EXTRACTION_VERSION} "
                    f"action={_action} type={type(exc).__name__} error={exc}"
                )
                raise
            finally:
                print(f"📷 [PHOTO_ACTION_EXIT] version={EXTRACTION_VERSION} action={_action}")

        child.callback = external_callback
        child._xiaoxia_external_handler = True
        child._xiaoxia_action_key = action_key
        wired.append(action_key)

    return {"wired": wired, "missing": missing, "count": len(wired)}


def install_photo_result_view_router(app: Any) -> Dict[str, Any]:
    current = getattr(app, "PhotoResultView", None)
    if current is None:
        raise RuntimeError("PhotoResultView is not available in stable runtime")

    stable_cls = getattr(app, "_V11202_STABLE_PHOTO_RESULT_VIEW_CLASS", None)
    if stable_cls is None:
        stable_cls = current
        app._V11202_STABLE_PHOTO_RESULT_VIEW_CLASS = stable_cls

    def routed_photo_result_view(context):
        view = stable_cls(context)
        dispatch = _wire_external_handlers(view, app)
        view._xiaoxia_dispatch_info = dispatch
        return view

    routed_photo_result_view.__name__ = "PhotoResultView"
    routed_photo_result_view.__qualname__ = "PhotoResultView"
    routed_photo_result_view.__doc__ = (
        "v1.12.02b external PhotoResultView router; all button business logic is "
        "owned by xiaoxia.photo.handlers."
    )
    app.PhotoResultView = routed_photo_result_view
    return {
        "version": EXTRACTION_VERSION,
        "stable_class": getattr(stable_cls, "__name__", type(stable_cls).__name__),
        "router": "xiaoxia.photo.actions",
        "callbacks_moved": True,
        "handler_owner": "xiaoxia.photo.handlers",
        "externalized": sorted(set(PHOTO_ACTION_KEYS.values())),
    }
