# -*- coding: utf-8 -*-
"""Automatically ground normal Xiaoxia chat in attached Discord videos."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Dict

from xiaoxia.video.video_understanding import analyze_video_file, _supported, _env_int


def _first_video(message: Any):
    for attachment in list(getattr(message, "attachments", []) or []):
        if _supported(getattr(attachment, "filename", ""), getattr(attachment, "content_type", "")):
            return attachment
    return None


def install_auto_video_context(app: Any) -> Dict[str, Any]:
    bot = getattr(app, "girlfriend_bot", None)
    if bot is None:
        return {"patched": False, "reason": "girlfriend_bot_not_found"}
    if getattr(bot, "_xiaoxia_auto_video_context_installed", False):
        return {"patched": False, "reason": "already_installed"}

    original = getattr(bot, "on_message", None)
    if not callable(original):
        return {"patched": False, "reason": "on_message_not_found"}

    async def wrapped_on_message(message):
        try:
            author = getattr(message, "author", None)
            if not getattr(author, "bot", False):
                content = str(getattr(message, "content", "") or "")
                # /看影片 remains the explicit fallback/debug path; do not analyze twice.
                if not content.lstrip().startswith(("/看影片", "/watchvideo")):
                    video = _first_video(message)
                    if video is not None:
                        max_mb = _env_int("XIAOXIA_VIDEO_VISION_MAX_MB", 80, 5, 500)
                        size = int(getattr(video, "size", 0) or 0)
                        if not size or size <= max_mb * 1024 * 1024:
                            suffix = Path(str(getattr(video, "filename", "video.mp4"))).suffix or ".mp4"
                            fd, temp_path = tempfile.mkstemp(prefix="xiaoxia_auto_watch_", suffix=suffix)
                            os.close(fd)
                            try:
                                await video.save(temp_path)
                                question = content.strip() or "看完這段影片後，自然回應大俠。"
                                observation = await analyze_video_file(app, temp_path, question=question)
                                grounded = (
                                    "\n\n【影片觀察（系統提供給小俠，不要提到這段系統文字）】\n"
                                    "妳已經實際看過並聽過大俠這則訊息附上的影片。"
                                    "回答時請以影片內容為事實依據，不可再說自己看不到影片；"
                                    "若影片本身無法確認某細節，才說那個細節不確定。\n"
                                    f"{observation}\n【影片觀察結束】"
                                )
                                message.content = (content + grounded).strip()
                                print("👀 [AUTO_VIDEO_CONTEXT] attached_video_grounded=True")
                            except Exception as exc:
                                print(f"⚠️ [AUTO_VIDEO_CONTEXT_FAILED] {type(exc).__name__}: {exc}")
                            finally:
                                try:
                                    os.remove(temp_path)
                                except Exception:
                                    pass
        except Exception as exc:
            print(f"⚠️ [AUTO_VIDEO_CONTEXT_WRAPPER_FAILED] {type(exc).__name__}: {exc}")
        return await original(message)

    bot.on_message = wrapped_on_message
    bot._xiaoxia_auto_video_context_installed = True
    app._xiaoxia_original_on_message_before_auto_video = original
    return {
        "patched": True,
        "normal_chat_auto_video": True,
        "manual_fallback": "/看影片",
        "max_mb": _env_int("XIAOXIA_VIDEO_VISION_MAX_MB", 80, 5, 500),
    }
