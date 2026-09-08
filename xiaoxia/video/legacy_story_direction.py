# -*- coding: utf-8 -*-
"""v1.12.06aa — let /影片 accept user plot direction while keeping Gemini as Director.

Usage:
  /影片
  /影片 <劇情>
  /影片 <劇情>｜<想說的話>

The user supplies intent, not a provider prompt. Gemini still converts the request
into one feasible 10-second Hero Action / Reaction / Camera plan from the replied
start frame and authoritative scene.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Tuple

from xiaoxia.video import h3_director_mode, legacy_archive_ui, legacy_command, voiceover_mode


def _split_direction(raw: str) -> Tuple[str, str]:
    text = str(raw or "").strip()
    if not text:
        return "", ""
    for sep in ("｜", "|"):
        if sep in text:
            left, right = text.split(sep, 1)
            return left.strip(), right.strip()
    return text, ""


def _inject_direction(context: Dict[str, Any], plot: str, spoken: str) -> Dict[str, Any]:
    ctx = dict(context or {})
    if not plot and not spoken:
        return ctx

    existing = str(ctx.get("message") or "").strip()
    pieces = []
    if plot:
        pieces.append(
            "大俠指定這支 10 秒影片的劇情意圖如下。這是創作方向，不是 provider prompt；"
            "請妳先檢查起始圖是否做得到，再收斂成一個清楚、自然、可完成的 Hero Action，"
            "必要時可簡化，但不要把核心意圖改掉：\n"
            f"【指定劇情】{plot}"
        )
    if spoken:
        pieces.append(
            "大俠另外指定想聽到的台詞如下。除非安全或長度明顯不適合，請優先保留語意與口吻；"
            "仍由目前 adaptive audio 規則判斷適合做 dialogue、voiceover 或必要的簡化：\n"
            f"【指定台詞】{spoken}"
        )
    ctx["message"] = "\n".join([p for p in (existing, *pieces) if p]).strip()
    ctx["video_user_direction"] = plot
    ctx["video_user_spoken_line"] = spoken
    return ctx


def install_legacy_story_direction(app: Any) -> Dict[str, Any]:
    bot = getattr(app, "girlfriend_bot", None)
    if bot is None:
        raise RuntimeError("girlfriend_bot not found")

    try:
        bot.remove_command("影片")
    except Exception:
        pass

    @bot.command(name="影片")
    async def directed_legacy_video(ctx, *, direction: str = ""):
        replied = await legacy_command._resolve_replied_message(ctx)
        if replied is None:
            await ctx.reply(
                "請先回覆一則小俠的圖片訊息，再輸入 `/影片`；也可以在後面直接寫劇情。",
                mention_author=False,
            )
            return

        context = legacy_command._context_from_runtime(app, replied) or legacy_command._context_from_message(replied)
        image_url = str(context.get("local_url") or context.get("image_url") or "").strip()
        local_path = str(context.get("local_path") or "").strip()
        if not image_url and not (local_path and os.path.exists(local_path)):
            await ctx.reply("這則訊息裡找不到可用的圖片，請回覆真正有小俠圖片的那一則。", mention_author=False)
            return

        plot, spoken = _split_direction(direction)
        directed_context = _inject_direction(context, plot, spoken)
        cfg = voiceover_mode._config()

        if plot or spoken:
            ack = [f"🎬 收到，用這張原圖生成 {cfg.get('duration')} 秒 H3 影片。"]
            if plot:
                ack.append(f"🎭 劇情：{plot[:180]}")
            if spoken:
                ack.append(f"🎙️ 指定台詞：{spoken[:100]}")
            ack.append("Gemini 會先把你的想法整理成適合這張起始圖的短片導演方案，再交給 H3。")
            await ctx.reply("\n".join(ack), mention_author=False)
        else:
            await ctx.reply(
                f"🎬 收到，這次讓 Gemini 自由導演，用你回覆的原圖生成 {cfg.get('duration')} 秒 H3 影片。",
                mention_author=False,
            )

        try:
            async with ctx.typing():
                result = await h3_director_mode._generate_h3_native_directed(app, directed_context)
            # Preserve the original photo context for archive lineage, but keep the
            # user direction so the saved record can explain how this clip was directed.
            archive_context = dict(context or {})
            if plot:
                archive_context["video_user_direction"] = plot
                archive_context["h3_video_theme"] = result.get("video_theme") or archive_context.get("h3_video_theme")
            if spoken:
                archive_context["video_user_spoken_line"] = spoken
            await legacy_archive_ui._send_legacy_with_archive(ctx, result, archive_context, app)
        except Exception as exc:
            print(f"❌ [H3_LEGACY_DIRECTED_ERROR] {type(exc).__name__}: {exc!r}")
            try:
                from xiaoxia.video import diagnostics
                await ctx.reply(diagnostics.format_h3_error(exc, cfg), mention_author=False)
            except Exception:
                await ctx.reply("⚠️ H3 影片生成失敗，請查看 Zeabur log。", mention_author=False)

    return {
        "patched": True,
        "command": "/影片 [劇情]｜[台詞]",
        "blank_means_free_director": True,
        "plot_is_upstream_intent": True,
        "gemini_still_directs": True,
        "provider_prompt_not_user_raw_text": True,
        "optional_spoken_line": True,
    }
