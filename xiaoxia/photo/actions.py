# -*- coding: utf-8 -*-
"""Photo action routing seam.

v1.12.02a moved PhotoResultView construction behind this module.
v1.12.02b1 additionally moves the dispatch boundary for the first three high-use
photo actions (More / dice replacement / full reroll) out of the monolith while
preserving the already-proven callback implementation byte-for-byte.

This is intentionally a strangler-style extraction: external ownership of routing
first, callback business logic second. It gives us a stable, observable seam before
we move generation code out of the 1.9 MB monolith.
"""
from __future__ import annotations

from functools import wraps
from typing import Any, Dict

EXTRACTION_VERSION = "1.12.02b1"

PHOTO_ACTION_KEYS = {
    "More": "more",
    "🎲 骰子取代": "dice_reroll",
    "🔄 重擲": "full_reroll",
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

# First extraction group.  Business logic still delegates to the stable implementation;
# dispatch ownership and observability now live here.
EXTERNAL_DISPATCH_ACTIONS = {
    "More": "more",
    "🎲 骰子取代": "dice_reroll",
    "🔄 重擲": "full_reroll",
}


def photo_action_key(label: str) -> str:
    """Canonical action key used by trace/lineage modules."""
    return PHOTO_ACTION_KEYS.get(str(label or "").strip(), "unknown")


def _wire_external_dispatch(view: Any) -> Dict[str, Any]:
    """Route selected Discord Button callbacks through this module.

    The original callback remains the implementation for b1.  Wrapping at the View
    instance boundary avoids rewriting the stable monolith and, importantly, also
    covers descendant PhotoResultViews created by More/reroll callbacks.
    """
    wired = []
    for child in list(getattr(view, "children", []) or []):
        label = str(getattr(child, "label", "") or "").strip()
        action_key = EXTERNAL_DISPATCH_ACTIONS.get(label)
        if not action_key:
            continue
        if getattr(child, "_xiaoxia_external_dispatch", False):
            continue

        original_callback = getattr(child, "callback", None)
        if original_callback is None:
            continue

        @wraps(original_callback)
        async def routed_callback(interaction, _original=original_callback, _action=action_key):
            print(f"📷 [PHOTO_ACTION_ENTER] version={EXTRACTION_VERSION} action={_action}")
            try:
                return await _original(interaction)
            except Exception as exc:
                print(
                    f"❌ [PHOTO_ACTION_ERROR] version={EXTRACTION_VERSION} "
                    f"action={_action} type={type(exc).__name__} error={exc}"
                )
                raise
            finally:
                print(f"📷 [PHOTO_ACTION_EXIT] version={EXTRACTION_VERSION} action={_action}")

        child.callback = routed_callback
        child._xiaoxia_external_dispatch = True
        child._xiaoxia_action_key = action_key
        wired.append(action_key)

    return {
        "wired": wired,
        "count": len(wired),
    }


def install_photo_result_view_router(app: Any) -> Dict[str, Any]:
    """Install external PhotoResultView construction + selected callback dispatch."""
    current = getattr(app, "PhotoResultView", None)
    if current is None:
        raise RuntimeError("PhotoResultView is not available in stable runtime")

    # Idempotent across import/reload within one process.  If 02a has already installed
    # a factory, use the stable class it saved rather than wrapping the factory itself.
    stable_cls = getattr(app, "_V11202_STABLE_PHOTO_RESULT_VIEW_CLASS", None)
    if stable_cls is None:
        stable_cls = current
        app._V11202_STABLE_PHOTO_RESULT_VIEW_CLASS = stable_cls

    def routed_photo_result_view(context):
        view = stable_cls(context)
        dispatch = _wire_external_dispatch(view)
        # Kept on the instance for runtime inspection without changing user-facing UI.
        view._xiaoxia_dispatch_info = dispatch
        return view

    routed_photo_result_view.__name__ = "PhotoResultView"
    routed_photo_result_view.__qualname__ = "PhotoResultView"
    routed_photo_result_view.__doc__ = (
        "v1.12.02b1 external PhotoResultView router; "
        "More/dice/full-reroll dispatch is owned by xiaoxia.photo.actions."
    )
    app.PhotoResultView = routed_photo_result_view
    return {
        "version": EXTRACTION_VERSION,
        "stable_class": getattr(stable_cls, "__name__", type(stable_cls).__name__),
        "router": "xiaoxia.photo.actions",
        "callbacks_moved": False,
        "dispatch_externalized": sorted(EXTERNAL_DISPATCH_ACTIONS.values()),
    }
