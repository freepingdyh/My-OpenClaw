# -*- coding: utf-8 -*-
"""v1.12.06n — shared H3 Director + native H3 off-screen narration.

One common video-directing layer for every Xiaoxia image source.
No module-specific strategy tables and no scene-action database.
Gemini reads the authoritative scene/context, first decides one short 10-second
video theme, then returns a compact plan. H3 receives a short prompt built from
that plan and generates motion + native Taiwanese-young-female-style voice-over
+ scene ambience in one pass.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict

import discord
from google.genai import types

from xiaoxia.video import h3, diagnostics, legacy_command, trace_store, voiceover_mode

_ALLOWED_MOTION = {"quiet", "natural", "dynamic"}


def _clean(app: Any, value: Any) -> str:
    return h3._clean(app, value)


def _scene(app: Any, context: Dict[str, Any]) -> str:
    return h3._scene_text(app, context)


def _json_object(text: str) -> Dict[str, Any]:
    raw = str(text or "").strip()
    try:
        obj = json.loads(raw)
        return obj if isinstance(obj, dict) else {}
    except Exception:
        pass
    m = re.search(r"\{.*\}", raw, flags=re.S)
    if not m:
        return {}
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else {}
    except Exception:
        return {}


def _normalize_plan(app: Any, context: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, str]:
    scene = _scene(app, context)
    theme = _clean(app, data.get("video_theme") or "")[:120]
    if not theme:
        theme = _clean(app, scene)[:80] or "小俠在當下場景裡自然地演出一個十秒小片段給大俠看。"

    motion = str(data.get("motion_level") or "natural").strip().lower()
    if motion not in _ALLOWED_MOTION:
        motion = "natural"

    hero = _clean(app, data.get("hero_action") or "")[:220]
    if not hero:
        hero = "She performs one clear, natural action that follows directly from her current pose and visible surroundings."

    reaction = _clean(app, data.get("reaction") or "")[:180]
    if not reaction:
        reaction = "She settles naturally and gives a brief genuine reaction toward the camera."

    camera = _clean(app, data.get("camera") or "")[:120]
    if not camera:
        camera = "mostly stable camera with only a subtle move if it helps the action"

    voice = _clean(app, data.get("voiceover") or "")[:96]
    if not voice:
        voice = "大俠，這一小段只演給你看喔。"

    ambience = _clean(app, data.get("ambience") or "")[:140]
    if not ambience:
        ambience = "natural ambience that belongs to the visible environment"

    return {
        "video_theme": theme,
        "motion_level": motion,
        "hero_action": hero,
        "reaction": reaction,
        "camera": camera,
        "voiceover": voice,
        "ambience": ambience,
    }


async def build_h3_director_plan(app: Any, context: Dict[str, Any], cfg: Dict[str, Any]) -> Dict[str, str]:
    scene = _scene(app, context)
    title = _clean(app, context.get("title") or context.get("activity_title") or "")
    message = _clean(app, context.get("message") or "")
    composition = _clean(app, context.get("composition") or "")

    director_prompt = f"""妳是「小俠」10 秒短影片的共用導演。所有來源模組都使用同一套原則，不要根據模組名稱套模板，也不要查任何場景動作資料庫。

先讀懂目前場景，再決定這 10 秒『到底要演什麼』。第一步一定要先產生一句簡短 video_theme，後面的動作、反應、鏡頭、旁白、環境音全部必須服務同一個主題，不能各自發散。

角色關係：小俠是在演給大俠看。旁白是小俠對大俠的內心戲／畫外音，不是主持、介紹、解說畫面，也不要把眼前看得到的內容逐句念出來。

導演原則：
1. 每支片只安排一個主要動作（Hero Action）+ 一個自然收尾反應 + 最多一個簡單 Camera Intent。
2. 不要預設只有眨眼、呼吸。若現有姿勢、道具、場景明顯支持一個有意義的身體動作，可以選 dynamic，讓她真的做一次較大的動作；不適合時才選 natural 或 quiet。
3. 大動作必須能從目前場景自然推導，不可憑空新增道具、換場景、換衣服或增加其他人物。
4. Hero Action 要單純、可在 10 秒內完成，不要同時塞很多事件。
5. 旁白約 12～30 個中文字，繁體中文，自然像 24 歲台灣女生心裡真的會講的話；可以自然稱呼大俠。少 AI 文案感、少空泛情話。
6. H3 會自行產生聲音，所以 ambience 只需簡短描述現場該有的聲音。
7. hero_action / reaction / camera / ambience 請用簡短英文，讓後續直接組成 H3 prompt；video_theme / voiceover 用繁體中文。

只輸出 JSON，不要解釋：
{{
  "video_theme": "一句 20～40 字左右的繁體中文影片主題",
  "motion_level": "quiet|natural|dynamic",
  "hero_action": "one concise English action, max ~24 words",
  "reaction": "one concise English reaction, max ~16 words",
  "camera": "one concise English camera intent, max ~12 words",
  "voiceover": "繁體中文內心旁白",
  "ambience": "concise English scene ambience, max ~12 words"
}}

目前標題：{title}
目前場景（SSOT）：{scene}
畫面補充：{composition}
關係／訊息補充：{message}
"""

    try:
        resp = await app.gemini_client.aio.models.generate_content(
            model=cfg["script_model"],
            contents=director_prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                temperature=0.55,
            ),
        )
        data = _json_object(getattr(resp, "text", "") or "")
    except Exception as exc:
        print(f"⚠️ [H3_DIRECTOR_FAILED] {type(exc).__name__}: {exc}")
        data = {}

    plan = _normalize_plan(app, context, data)
    context["h3_director_plan"] = dict(plan)
    context["h3_video_theme"] = plan["video_theme"]
    context["h3_motion_level"] = plan["motion_level"]

    try:
        trace = trace_store._TRACE_CTX.get()
        if trace is not None:
            trace["video_theme"] = plan["video_theme"]
            trace["motion_level"] = plan["motion_level"]
            trace["director_plan"] = dict(plan)
            trace_store._stage(app, trace, "h3_director_plan", dict(plan), snapshot=True)
    except Exception as exc:
        print(f"⚠️ [H3_DIRECTOR_TRACE_WARN] {type(exc).__name__}: {exc}")

    print(
        "🎬 [H3_DIRECTOR_PLAN] "
        f"motion={plan['motion_level']} theme={plan['video_theme']!r} "
        f"voiceover={plan['voiceover']!r}"
    )
    return plan


def build_compact_h3_prompt(plan: Dict[str, str], *, minimal: bool = False) -> str:
    if minimal:
        return (
            "Use Image 1 as the same woman and the same place. "
            f"Action: {plan['hero_action']} Then: {plan['reaction']} "
            "The woman on screen does not speak or lip-sync. "
            "Off-screen Traditional Chinese voice-over by a young Taiwanese woman, natural, lively, bright and warm: "
            f'\"{plan["voiceover"]}\". '
            f"Natural ambience: {plan['ambience']}. No subtitles. No music."
        )

    motion_note = {
        "quiet": "Keep the movement gentle but purposeful.",
        "natural": "Use natural readable body motion, not just blinking and breathing.",
        "dynamic": "Let the main action be clearly visible and energetic, while keeping it physically coherent with the starting pose.",
    }[plan["motion_level"]]

    return (
        "Image 1 is the exact visual identity and starting frame. "
        f"10-second theme: {plan['video_theme']} "
        f"Main action: {plan['hero_action']} {motion_note} "
        f"Reaction: {plan['reaction']} "
        f"Camera: {plan['camera']}. "
        "Keep the same woman, face, outfit and location; do not add people or text. "
        "The woman visible on screen does NOT speak and does NOT lip-sync. "
        "Use native off-screen voice-over narration in Traditional Chinese, spoken by a young Taiwanese woman: lively, bright, warm, natural, slightly magnetic, never announcer-like. "
        f'Voice-over line: \"{plan["voiceover"]}\". '
        f"Native ambience: {plan['ambience']}. No subtitles. No music."
    )


async def _generate_h3_native_directed(app: Any, context: Dict[str, Any]) -> Dict[str, Any]:
    cfg = voiceover_mode._config()
    plan = await build_h3_director_plan(app, context, cfg)
    image_url = await h3._ensure_image_url(app, context)
    model_id = cfg["image_model"]

    args = {
        "prompt": build_compact_h3_prompt(plan),
        "duration": cfg["duration"],
        "resolution": cfg["resolution"],
        "enable_safety_checker": cfg["safety"],
        "prompt_expansion_mode": cfg["expansion"],
        "image_url": image_url,
    }

    try:
        result = await voiceover_mode._subscribe(app, model_id, args, "H3_DIRECTOR_NATIVE_QUEUE")
    except Exception as exc:
        info = diagnostics.extract_h3_error(exc)
        if (
            str(info.get("type") or "").lower() == "content_policy_violation"
            and str(info.get("loc") or "").lower() == "body.prompt"
        ):
            args["prompt"] = build_compact_h3_prompt(plan, minimal=True)
            result = await voiceover_mode._subscribe(app, model_id, args, "H3_DIRECTOR_NATIVE_MINIMAL_QUEUE")
        else:
            raise

    video = result.get("video") if isinstance(result, dict) else None
    url = video.get("url") if isinstance(video, dict) else None
    if not url:
        raise RuntimeError(f"H3_DIRECTOR_NO_URL: {result}")
    path, filename, public = await h3._download_video(app, url)
    if not path:
        raise RuntimeError("H3_DIRECTOR_DOWNLOAD_FAILED")

    return {
        "model_id": model_id,
        "video_url": url,
        "local_path": path,
        "local_filename": filename,
        "local_url": public,
        "voice_script": plan["voiceover"],
        "used_voice": True,
        "voice_mode": "voiceover_h3_native",
        "duration": cfg["duration"],
        "resolution": cfg["resolution"],
        "ambient_audio": True,
        "video_theme": plan["video_theme"],
        "motion_level": plan["motion_level"],
        "director_plan": plan,
    }


async def _send_success_interaction(view, interaction: discord.Interaction, result: Dict[str, Any]) -> None:
    cfg = voiceover_mode._config()
    lines = ["🎬 **H3影片生成完成**", f"規格：{result.get('duration')} 秒｜{result.get('resolution')}"]
    if result.get("video_theme"):
        lines.append(f"🎞️ 主題：{result.get('video_theme')}")
    if result.get("motion_level"):
        lines.append(f"🎭 動作：{result.get('motion_level')}")
    if result.get("voice_script"):
        lines.append(f"🎙️ H3 原生旁白：{result.get('voice_script')}")
    if result.get("ambient_audio"):
        lines.append("🌿 H3 原生場景音")

    path = str(result.get("local_path") or "")
    max_bytes = int(cfg.get("send_file_max_mb") or 24) * 1024 * 1024
    if path and os.path.exists(path) and os.path.getsize(path) <= max_bytes:
        await interaction.followup.send("\n".join(lines), file=discord.File(path, filename=os.path.basename(path)))
    else:
        link = result.get("local_url") or result.get("video_url")
        if link:
            lines.append(f"📎 {link}")
        await interaction.followup.send("\n".join(lines))
    view.context["last_h3_video_url"] = result.get("local_url") or result.get("video_url")
    view.context["last_h3_video_model_id"] = result.get("model_id")
    view.context["last_h3_voice_script"] = result.get("voice_script") or ""


async def _send_success_ctx(ctx, result: Dict[str, Any]) -> None:
    cfg = voiceover_mode._config()
    lines = ["🎬 **H3影片生成完成**", f"規格：{result.get('duration')} 秒｜{result.get('resolution')}"]
    if result.get("video_theme"):
        lines.append(f"🎞️ 主題：{result.get('video_theme')}")
    if result.get("motion_level"):
        lines.append(f"🎭 動作：{result.get('motion_level')}")
    if result.get("voice_script"):
        lines.append(f"🎙️ H3 原生旁白：{result.get('voice_script')}")
    lines.append("🌿 H3 原生場景音")

    path = str(result.get("local_path") or "")
    max_bytes = int(cfg.get("send_file_max_mb") or 24) * 1024 * 1024
    if path and os.path.exists(path) and os.path.getsize(path) <= max_bytes:
        await ctx.reply("\n".join(lines), file=discord.File(path, filename=os.path.basename(path)), mention_author=False)
    else:
        link = result.get("local_url") or result.get("video_url")
        if link:
            lines.append(f"📎 {link}")
        await ctx.reply("\n".join(lines), mention_author=False)


def install_h3_director_mode(app: Any) -> Dict[str, Any]:
    if getattr(voiceover_mode, "_xiaoxia_h3_director_mode_installed", False):
        return {"patched": False, "reason": "already_installed"}

    trace_store._ORIGINAL_GENERATE = _generate_h3_native_directed
    diagnostics._send_success_to_interaction = _send_success_interaction
    legacy_command._send_video_result = _send_success_ctx

    app.h3_build_director_plan = lambda context: build_h3_director_plan(app, context, voiceover_mode._config())
    voiceover_mode._xiaoxia_h3_director_mode_installed = True
    return {
        "patched": True,
        "director": "shared Gemini H3 Director",
        "module_specific_rules": False,
        "scene_database": False,
        "theme_first": True,
        "primary_voice": "H3 native off-screen Traditional Chinese narration",
        "voice_style": "young Taiwanese woman; lively, bright, warm, natural, slightly magnetic",
        "motion_levels": "quiet|natural|dynamic",
        "hero_action_rule": "one Hero Action + one Reaction + max one Camera Intent",
        "trace_preserved": True,
        "retry_preserved": True,
    }
