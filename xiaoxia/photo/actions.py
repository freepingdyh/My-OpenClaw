# -*- coding: utf-8 -*-
"""Photo action routing seam for v1.12.02a.

Checkpoint goal: make PhotoResultView construction externally owned before moving its
large callbacks. The stable v1.11.17.2 View remains the implementation in 02a.
02b can replace the implementation behind this seam without touching dozens of callers.
"""
from __future__ import annotations

from typing import Any, Callable, Dict

EXTRACTION_VERSION = "1.12.02a"

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


def photo_action_key(label: str) -> str:
    """Canonical action key used by trace/lineage modules."""
    return PHOTO_ACTION_KEYS.get(str(label or "").strip(), "unknown")


def install_photo_result_view_router(app: Any) -> Dict[str, Any]:
    """Install an external construction seam while preserving the stable View class.

    All existing monolith call sites resolve the module global ``PhotoResultView`` at
    runtime. Replacing that symbol with this factory routes both top-level and recursive
    descendant View creation through this module while returning the exact stable class.
    No Discord button callback is rewritten in checkpoint 02a.
    """
    current = getattr(app, "PhotoResultView", None)
    if current is None:
        raise RuntimeError("PhotoResultView is not available in stable runtime")

    # Idempotent across import/reload within one process.
    stable_cls = getattr(app, "_V11202_STABLE_PHOTO_RESULT_VIEW_CLASS", None)
    if stable_cls is None:
        stable_cls = current
        app._V11202_STABLE_PHOTO_RESULT_VIEW_CLASS = stable_cls

    def routed_photo_result_view(context):
        return stable_cls(context)

    routed_photo_result_view.__name__ = "PhotoResultView"
    routed_photo_result_view.__qualname__ = "PhotoResultView"
    routed_photo_result_view.__doc__ = (
        "v1.12.02a external PhotoResultView construction router; "
        "returns the stable Discord View implementation."
    )
    app.PhotoResultView = routed_photo_result_view
    return {
        "version": EXTRACTION_VERSION,
        "stable_class": getattr(stable_cls, "__name__", type(stable_cls).__name__),
        "router": "xiaoxia.photo.actions",
        "callbacks_moved": False,
    }
