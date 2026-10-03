# -*- coding: utf-8 -*-
"""Xiaoxia watches a Discord video with Gemini multimodal understanding.

This is a bounded capability: it does not reinterpret authoritative_scene and it is
not part of H3 Director. The same analyzer can later be reused for Xiaoxia's own
archived H3 clips.
"""
from __future__ import annotations

import asyncio
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Optional

from google.genai import types

from xiaoxia.video.model_refresh import video_vision_model

_SUPPORTED_MIME = {
    "video/mp4", "video/mpeg", "video/mov", "video/avi", "video/x-flv",
    "video/mpg", "video/webm", "video/wmv", "video/3gpp",
}
_SUPPORTED_EXT = {".mp4", ".mpeg", ".mpg", ".mov", ".avi", ".flv", ".webm", ".wmv", ".3gp"}


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(os.environ.get(name, default)).strip())
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def _supported(filename: str, content_type: str) -> bool:
    mime = str(content_type or "").split(";", 1)[0].strip().lower()
    ext = Path(str(filename or "")).suffix.lower()
    return mime in _SUPPORTED_MIME or ext in _SUPPORTED_EXT


def _prompt(question: str) -> str:
    q = " ".join(str(question or "").split()).strip()
    if not q:
        q = "看完後告訴大俠妳最注意到什麼，以及妳對這段影片的自然感想。"
    return f"""妳是小俠，大俠剛傳了一段影片給妳看。
請真的根據影片的畫面與聲音回答，不可假裝看到影片裡沒有的內容；不確定時就直接說不確定。
回答用繁體中文，像 24 歲台灣女生自然跟大俠聊天，不要寫成制式影片分析報告。
若大俠問到某個動作、事件或關鍵瞬間，可自然附上 MM:SS 時間點；不要為了顯得專業而硬塞時間戳。
先回答大俠真正想知道的事，再補一兩個妳自己覺得值得注意的細節。簡潔自然即可。

大俠想問：{q}
"""


async def _wait_active(client: Any, uploaded: Any, timeout_sec: int = 180):
    deadline = asyncio.get_running_loop().time() + timeout_sec
    current = uploaded
    while True:
        state = getattr(getattr(current, "state", None), "name", None)
        if not state:
            state = str(getattr(current, "state", "") or "").upper()
        state = str(state or "").upper()
        if state == "ACTIVE":
            return current
        if state == "FAILED":
            raise RuntimeError("GEMINI_VIDEO_FILE_PROCESSING_FAILED")
        if asyncio.get_running_loop().time() >= deadline:
            raise TimeoutError("GEMINI_VIDEO_FILE_PROCESSING_TIMEOUT")
        await asyncio.sleep(3)
        current = await asyncio.to_thread(client.files.get, name=current.name)


async def analyze_video_file(app: Any, path: str, *, question: str = "") -> str:
    client = getattr(app, "gemini_client", None)
    if client is None:
        raise RuntimeError("gemini_client not found")

    uploaded = None
    try:
        uploaded = await asyncio.to_thread(client.files.upload, file=path)
        uploaded = await _wait_active(client, uploaded)
        config = types.GenerateContentConfig(temperature=0.65)
        response = await client.aio.models.generate_content(
            model=video_vision_model(),
            contents=[uploaded, _prompt(question)],
            config=config,
        )
        text = str(getattr(response, "text", "") or "").strip()
        if not text:
            raise RuntimeError("GEMINI_VIDEO_EMPTY_RESPONSE")
        return text
    finally:
        if uploaded is not None and getattr(uploaded, "name", None):
            try:
                await asyncio.to_thread(client.files.delete, name=uploaded.name)
            except Exception:
                pass


def _chunks(text: str, limit: int = 1900) -> list[str]:
    src = str(text or "").strip()
    if len(src) <= limit:
        return [src]
    out = []
    while src:
        if len(src) <= limit:
            out.append(src)
            break
        cut = src.rfind("\n", 0, limit)
        if cut < limit // 2:
            cut = src.rfind("。", 0, limit)
        if cut < limit // 2:
            cut = limit
        else:
            cut += 1
        out.append(src[:cut].strip())
        src = src[cut:].strip()
    return [x for x in out if x]


def install_video_understanding(app: Any) -> Dict[str, Any]:
    bot = getattr(app, "girlfriend_bot", None)
    if bot is None:
        raise RuntimeError("girlfriend_bot not found")

    bot.remove_command("看影片")
    bot.remove_command("watchvideo")

    @bot.command(name="看影片", aliases=["watchvideo"])
    async def watch_video_command(ctx, *, question: str = ""):
        attachments = list(getattr(getattr(ctx, "message", None), "attachments", []) or [])
        video = next(
            (a for a in attachments if _supported(getattr(a, "filename", ""), getattr(a, "content_type", ""))),
            None,
        )
        if video is None:
            await ctx.reply(
                "大俠，把影片和 `/看影片` 放在同一則訊息裡給我呀～也可以在後面加問題，例如 `/看影片 你覺得這支 H3 自然嗎？`",
                mention_author=False,
            )
            return

        max_mb = _env_int("XIAOXIA_VIDEO_VISION_MAX_MB", 80, 5, 500)
        size = int(getattr(video, "size", 0) or 0)
        if size and size > max_mb * 1024 * 1024:
            await ctx.reply(f"這支影片超過目前 {max_mb} MB 的看片上限。", mention_author=False)
            return

        suffix = Path(str(getattr(video, "filename", "video.mp4"))).suffix or ".mp4"
        fd, temp_path = tempfile.mkstemp(prefix="xiaoxia_watch_", suffix=suffix)
        os.close(fd)
        try:
            async with ctx.typing():
                await video.save(temp_path)
                answer = await analyze_video_file(app, temp_path, question=question)
            parts = _chunks(answer)
            for i, part in enumerate(parts):
                if i == 0:
                    await ctx.reply(part, mention_author=False)
                else:
                    await ctx.send(part)
        except Exception as exc:
            print(f"❌ [XIAOXIA_VIDEO_UNDERSTANDING_FAILED] {type(exc).__name__}: {exc}")
            await ctx.reply("我這次沒有把影片看成功，再給我一次這支影片好嗎？", mention_author=False)
        finally:
            try:
                os.remove(temp_path)
            except Exception:
                pass

    app.xiaoxia_analyze_video_file = lambda path, question="": analyze_video_file(app, path, question=question)
    return {
        "patched": True,
        "command": "/看影片 [問題] + 同訊息影片附件",
        "model": video_vision_model(),
        "supported": sorted(_SUPPORTED_EXT),
        "max_mb": _env_int("XIAOXIA_VIDEO_VISION_MAX_MB", 80, 5, 500),
        "reusable_analyzer": True,
    }
