# -*- coding: utf-8 -*-
"""Adaptive H3 audio direction: narration by default, selective direct dialogue, or ambience only."""
from __future__ import annotations

from typing import Any, Dict

from google.genai import types

from xiaoxia.video import h3_director_mode

_ALLOWED_AUDIO = {"voiceover", "dialogue", "ambience"}
_ORIGINAL_BUILD = h3_director_mode.build_h3_director_plan
_ORIGINAL_PROMPT = h3_director_mode.build_compact_h3_prompt


def _audio_prompt(plan: Dict[str, str], *, minimal: bool = False) -> str:
    mode = str(plan.get("audio_mode") or "voiceover").strip().lower()
    if mode not in _ALLOWED_AUDIO:
        mode = "voiceover"
    action = plan.get("hero_action") or "She performs one clear natural action."
    reaction = plan.get("reaction") or "She settles naturally toward the camera."
    line = plan.get("voiceover") or ""
    ambience = plan.get("ambience") or "natural ambience"
    identity = "Keep the same woman, face, hairstyle, outfit, body proportions and location; do not add people, text, subtitles, logos or watermarks. "
    core = f"Image 1 is the exact visual identity and starting frame. Main action: {action} Then: {reaction}. {identity}"

    if mode == "dialogue":
        return core + (
            "This is a rare direct-to-Daxia character moment. The visible Xiaoxia herself speaks the following Traditional Chinese line with natural, restrained lip sync. "
            "Use a young Taiwanese female voice: intimate, lively, warm and natural, never announcer-like. Do not add extra dialogue. "
            f'Xiaoxia says: "{line}". Natural ambience: {ambience}. No music.'
        )
    if mode == "ambience":
        return core + (
            "No dialogue and no narration. Xiaoxia remains naturally silent; do not make her mouth words or lip-sync. "
            f"Use only scene-appropriate native ambience: {ambience}. No music."
        )
    return core + (
        "The visible Xiaoxia remains silent and never lip-syncs. The voice is completely off-screen, non-diegetic inner narration and is not produced by the visible woman. "
        "Use a young Taiwanese female Traditional Chinese voice: intimate, lively, bright and natural, never announcer-like. "
        f'Off-screen line: "{line}". Natural ambience: {ambience}. No music.'
    )


async def build_adaptive_plan(app: Any, context: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, str]:
    plan = await _ORIGINAL_BUILD(app, context, cfg)
    scene = h3_director_mode._scene(app, context)
    title = h3_director_mode._clean(app, context.get("title") or context.get("activity_title") or "")
    message = h3_director_mode._clean(app, context.get("message") or "")
    prompt = f"""妳是小俠 10 秒短影片的聲音導演。請只決定聲音表演方式，不改動既有影片主題與動作。

可選 audio_mode：
- voiceover：預設。小俠本人不開口，以畫外內心旁白對大俠說話。
- dialogue：少數真正適合角色演出、直視大俠、Cosplay/戲劇性動作，且一句本人台詞會明顯讓角色更活時才選。畫面中的小俠本人自然開口並 lip-sync。
- ambience：畫面本身已足夠有力量、沉浸或安靜，說話反而破壞氣氛時選。完全無台詞，只有環境音。

重要：不要因為是 Cosplay 就固定 dialogue；不要為了變化而輪流選。若沒有明確理由，選 voiceover。
台詞若需要，12～30 個繁體中文字，像 24 歲台灣女生自然對大俠說話，少 AI 文案感。
只輸出 JSON：{{"audio_mode":"voiceover|dialogue|ambience","line":"繁體中文台詞；ambience 可空白"}}

標題：{title}
場景：{scene}
影片主題：{plan.get('video_theme','')}
主要動作：{plan.get('hero_action','')}
收尾反應：{plan.get('reaction','')}
原導演旁白：{plan.get('voiceover','')}
補充：{message}
"""
    try:
        resp = await app.gemini_client.aio.models.generate_content(
            model=cfg["script_model"], contents=prompt,
            config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.35),
        )
        data = h3_director_mode._json_object(getattr(resp, "text", "") or "")
        mode = str(data.get("audio_mode") or "voiceover").strip().lower()
        if mode not in _ALLOWED_AUDIO:
            mode = "voiceover"
        line = h3_director_mode._clean(app, data.get("line") or "")[:96]
        if mode != "ambience" and line:
            plan["voiceover"] = line
        plan["audio_mode"] = mode
    except Exception as exc:
        print(f"⚠️ [H3_ADAPTIVE_AUDIO_FAILED] {type(exc).__name__}: {exc}")
        plan["audio_mode"] = "voiceover"
    context["h3_director_plan"] = dict(plan)
    print(f"🎙️ [H3_ADAPTIVE_AUDIO] mode={plan['audio_mode']} line={plan.get('voiceover','')!r}")
    return plan


def install_adaptive_audio(app: Any) -> Dict[str, Any]:
    if getattr(app, "_xiaoxia_h3_adaptive_audio_installed", False):
        return {"patched": False, "reason": "already_installed"}
    h3_director_mode.build_h3_director_plan = build_adaptive_plan
    h3_director_mode.build_compact_h3_prompt = _audio_prompt
    app._xiaoxia_h3_adaptive_audio_installed = True
    return {"patched": True, "default": "voiceover", "choices": ["voiceover", "dialogue", "ambience"], "dialogue": "director_only_when_worth_it"}
