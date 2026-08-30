# -*- coding: utf-8 -*-
"""Gemini scene-fidelity guard for Xiaoxia's scene-only image contract.

v1.12.04 deliberately does NOT add a second prompt source to Seedream.
The downstream image pipeline continues to consume only authoritative_scene.
This module only asks Gemini to verify that the scene it wrote faithfully
preserves Daxia's explicit visual instructions, and repairs that same scene
when concrete pose/composition details were omitted or weakened.
"""
from __future__ import annotations

EXTRACTION_VERSION = "1.12.04"
_APP = None
_ORIGINAL_PHOTO_SCENE_WRITER = None


def _clean(value):
    app = _APP
    if app is None:
        return str(value or "").strip()
    return app._clean_text_compact(value or "")


async def _review_photo_scene_fidelity(raw_scene_text, scene_data):
    """Return the same scene_data shape, repairing only authoritative_scene if needed."""
    app = _APP
    raw_request = _clean(raw_scene_text)
    if app is None or not raw_request or not isinstance(scene_data, dict):
        return scene_data

    authoritative = _clean(
        scene_data.get("authoritative_scene")
        or scene_data.get("photo_prompt")
        or scene_data.get("scene_summary")
        or ""
    )
    if not authoritative:
        return scene_data

    review_prompt = f"""
你是「小俠場景忠實度審查員」，不是第二個創意導演。
系統的唯一視覺真相是 authoritative_scene；Seedream 與所有後續模組都只會看到這一段。
你的任務只有一個：確認 Gemini 已寫出的 authoritative_scene 是否忠實保留大俠本次明確指定的可視化要求。

【大俠本次原始指定】
{raw_request}

【Gemini 目前寫出的 authoritative_scene】
{authoritative}

請只回傳 JSON：
{{
  "verdict": "pass 或 repair",
  "missing_or_weakened": ["被漏掉、被模糊化或被改寫到失去可執行性的明確要求"],
  "authoritative_scene": "若 pass，原文照抄；若 repair，只修正同一段場景，使大俠所有明確可視要求清楚、具體、可畫",
  "reason": "一句話說明"
}}

審查規則：
1. 大俠明確指定的場景、人物位置、坐姿/站姿、身體角度、腿部姿勢、手的位置、視線、表情、鏡頭構圖、服裝要求，都是高優先級視覺事實；不得因為潤飾文字而省略、弱化或換成 generic pose。
2. 「雙腿打開／併攏／交疊」、「身體後傾／前傾」、「左/右手放在哪裡」、「看向哪裡」這類具體姿勢，必須在 authoritative_scene 中以同等明確程度保留，不能只縮寫成「自然坐姿」「慵懶姿勢」。
3. 若原始指定已經具體，忠實度優先於文采；scene 必須是 Seedream 可以直接執行的可視描述，而不是漂亮但模糊的散文摘要。
4. 不要新增大俠沒有要求的第二人物、肢體、場景或新動作；不要改變既有衣櫃服裝與場景核心。
5. 若目前 scene 已完整保留原始要求，verdict=pass 並原文照抄，不要為改而改。
6. 若需要 repair，只能修「這一份 authoritative_scene」；不得建立額外 prompt、hidden constraint 或第二視覺來源。
7. 姿勢仍需符合正常人體結構；在此前提下，不要自行把具體姿勢變得更保守、更籠統或更普通。
"""
    try:
        resp = await app.gemini_client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=review_prompt,
            config=app.types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.0,
            ),
        )
        review = app._extract_json_object(resp.text)
        if not isinstance(review, dict):
            print("⚠️ [SCENE_FIDELITY_REVIEW_FAILED] source=photo reason=invalid_json")
            return scene_data

        verdict = _clean(review.get("verdict")).lower()
        repaired = _clean(review.get("authoritative_scene"))
        missing = review.get("missing_or_weakened") or []
        if not isinstance(missing, list):
            missing = [str(missing)] if missing else []
        missing_compact = " | ".join(_clean(x) for x in missing if _clean(x))[:500]

        if verdict == "repair" and repaired:
            scene_data = dict(scene_data)
            scene_data["authoritative_scene"] = repaired
            scene_data["photo_prompt"] = repaired
            scene_data["scene_fidelity"] = {
                "version": EXTRACTION_VERSION,
                "verdict": "repair",
                "missing_or_weakened": missing[:12],
                "reason": _clean(review.get("reason"))[:300],
            }
            print(
                "🛠️ [SCENE_FIDELITY_REPAIRED] "
                f"source=photo missing={missing_compact or 'unspecified'}"
            )
            return scene_data

        print("🎯 [SCENE_FIDELITY_PASS] source=photo")
        scene_data = dict(scene_data)
        scene_data["scene_fidelity"] = {
            "version": EXTRACTION_VERSION,
            "verdict": "pass",
            "missing_or_weakened": [],
            "reason": _clean(review.get("reason"))[:300],
        }
        return scene_data
    except Exception as exc:
        print(f"⚠️ [SCENE_FIDELITY_REVIEW_FAILED] source=photo {type(exc).__name__}: {exc}")
        return scene_data


async def _photo_scene_writer_with_fidelity(*args, **kwargs):
    original = _ORIGINAL_PHOTO_SCENE_WRITER
    if original is None:
        raise RuntimeError("original photo scene writer is not installed")
    scene_data = await original(*args, **kwargs)
    raw_scene_text = kwargs.get("raw_scene_text")
    if raw_scene_text is None and args:
        raw_scene_text = args[0]
    return await _review_photo_scene_fidelity(raw_scene_text, scene_data)


def install_scene_fidelity(app):
    """Patch only the Gemini photo scene-writer boundary; Seedream contract stays scene-only."""
    global _APP, _ORIGINAL_PHOTO_SCENE_WRITER
    _APP = app

    existing = getattr(app, "_summarize_scene_for_photo", None)
    if existing is None:
        raise RuntimeError("_summarize_scene_for_photo not found")

    if getattr(existing, "_scene_fidelity_v11204", False):
        return {
            "module": "xiaoxia.scene.fidelity",
            "patched": "_summarize_scene_for_photo",
            "scene_ssot": "authoritative_scene",
            "already_installed": True,
        }

    _ORIGINAL_PHOTO_SCENE_WRITER = existing
    _photo_scene_writer_with_fidelity._scene_fidelity_v11204 = True
    _photo_scene_writer_with_fidelity._scene_fidelity_original = existing
    app._V11204_ORIGINAL_PHOTO_SCENE_WRITER = existing
    app._summarize_scene_for_photo = _photo_scene_writer_with_fidelity

    return {
        "module": "xiaoxia.scene.fidelity",
        "patched": "_summarize_scene_for_photo",
        "scene_ssot": "authoritative_scene",
        "already_installed": False,
    }
