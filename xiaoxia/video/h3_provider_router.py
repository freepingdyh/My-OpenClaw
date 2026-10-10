# -*- coding: utf-8 -*-
"""Provider routing primitives for Xiaoxia H3 video generation.

Prepared but NOT installed into xiaoxia_runtime_flat.py yet.

UX contract:
- fal.ai: use fal.ai only; failure is returned to the user.
- RunPod: use open-weight H3 on RunPod only; failure is returned to the user.
- auto: try fal.ai first, then immediately fall back to RunPod on final failure.
  Auto never asks for a second confirmation.

Provider selection is intentionally independent from scene semantics.  Ordinary
and derivative images may use either provider; story continuity belongs to the
Director/context layer, not to the backend router.
"""
from __future__ import annotations

from typing import Any, Awaitable, Callable, Dict

ProviderFn = Callable[[], Awaitable[Dict[str, Any]]]

PROVIDER_FAL = "fal"
PROVIDER_RUNPOD = "runpod"
PROVIDER_AUTO = "auto"


def normalize_provider(value: Any) -> str:
    raw = str(value or "").strip().lower()
    aliases = {
        "fal.ai": PROVIDER_FAL,
        "fal": PROVIDER_FAL,
        "minimax": PROVIDER_FAL,
        "runpod": PROVIDER_RUNPOD,
        "runpod+h3": PROVIDER_RUNPOD,
        "runpod_h3": PROVIDER_RUNPOD,
        "自動": PROVIDER_AUTO,
        "auto": PROVIDER_AUTO,
    }
    provider = aliases.get(raw, raw)
    if provider not in {PROVIDER_FAL, PROVIDER_RUNPOD, PROVIDER_AUTO}:
        raise ValueError(f"Unsupported H3 provider: {value!r}")
    return provider


async def route_h3_provider(
    requested: Any,
    *,
    fal_renderer: ProviderFn,
    runpod_renderer: ProviderFn,
) -> Dict[str, Any]:
    """Route one H3 render without any UI or Discord dependency."""
    provider = normalize_provider(requested)
    attempted: list[str] = []

    async def _call(name: str, renderer: ProviderFn) -> Dict[str, Any]:
        attempted.append(name)
        result = await renderer()
        if not isinstance(result, dict):
            raise RuntimeError(f"H3 provider {name} returned non-dict result")
        merged = dict(result)
        merged["provider_requested"] = provider
        merged["provider_attempted"] = list(attempted)
        merged["provider_final"] = name
        return merged

    if provider == PROVIDER_FAL:
        return await _call(PROVIDER_FAL, fal_renderer)

    if provider == PROVIDER_RUNPOD:
        return await _call(PROVIDER_RUNPOD, runpod_renderer)

    fal_error: Exception | None = None
    try:
        return await _call(PROVIDER_FAL, fal_renderer)
    except Exception as exc:
        fal_error = exc

    try:
        result = await _call(PROVIDER_RUNPOD, runpod_renderer)
        result["auto_fallback"] = True
        result["fal_failure_type"] = type(fal_error).__name__ if fal_error else None
        result["fal_failure_message"] = str(fal_error or "")[:1500]
        return result
    except Exception as runpod_error:
        error = RuntimeError(
            "H3 auto mode failed on both providers: "
            f"fal.ai={type(fal_error).__name__}: {str(fal_error)[:600]}; "
            f"RunPod={type(runpod_error).__name__}: {str(runpod_error)[:600]}"
        )
        setattr(error, "provider_requested", PROVIDER_AUTO)
        setattr(error, "provider_attempted", list(attempted))
        setattr(error, "fal_error", fal_error)
        setattr(error, "runpod_error", runpod_error)
        raise error from runpod_error


def build_solo_continuation_contract(*, inherit_scene: bool = False) -> str:
    """Chinese natural-language contract appended by the future H3 Director.

    Keep programmatic keys in English, but user/model-facing rules in Chinese.
    This deliberately stays non-explicit: sensuality can be conveyed by the
    subject's own expression and movement while the clip remains solo.
    """
    parts = [
        "【單人主體鎖定】",
        "整段影片只允許出現小俠一人。",
        "禁止出現任何男性、第二位女性、其他人的臉、手、手臂、腿、軀幹、身影、倒影、陰影人物或其他身體部位。",
        "不得暗示有看不見的第二人正在碰觸、抓住、控制或與小俠發生身體互動。",
        "不得生成性交或明確性行為。",
        "可以呈現魅惑、挑逗、曖昧、自信、害羞、歡愉或情緒升溫；親密感只能透過小俠自己的眼神、表情、姿勢、動作、自我整理與身體語言表現。",
        "目前圖片是影片第 1 幀的視覺真實來源；保持同一人物、場景、鏡頭與空間連續性，不新增人物。",
    ]
    if inherit_scene:
        parts.extend([
            "",
            "【場景延續規則】",
            "目前圖片不是新的獨立場景，而是原本場景的後續瞬間。",
            "目前圖片中的人物姿勢、鏡頭、場景、空間關係與目前人物狀態，視為影片第 1 幀的真實狀態。",
            "人物狀態的改變視為已在影片開始前完成；不要解釋改變的原因，也不要重新開啟新的場景。",
            "延續原本場景的地點、空間關係、家具與道具、情緒氛圍及故事脈絡，從目前這一幀自然往後發展。",
        ])
    return "\n".join(parts).strip()
