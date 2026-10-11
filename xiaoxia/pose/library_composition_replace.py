# -*- coding: utf-8 -*-
"""v1.13.06 — Pose Library Composition visibility, trace persistence, manual edit fix.

Keeps the proven 8+Pose+Wardrobe reference contract unchanged while making
Composition observable end-to-end:
1) persist Gemini's observed composition_feature and reuse it for library poses;
2) `/姿勢 修正 Pxxx` with an attached image replaces only that pose reference image;
3) `/姿勢 看` and `/姿勢 修正 ... 重新判讀` visibly echo Composition;
4) `/photo` trace/context records pose_composition_feature explicitly;
5) manual `Composition=...` is parsed as composition_feature and never swallowed by Pose.
"""
from __future__ import annotations

import os
import re
from datetime import datetime
from typing import Any, Dict

import discord

from xiaoxia.pose import core as pose_core

VERSION = "1.13.06"
_STATE_KEY = "photo_pending_pose_reference"
_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def _is_image_attachment(a: Any) -> bool:
    ct = str(getattr(a, "content_type", "") or "").lower()
    fn = str(getattr(a, "filename", "") or "").lower()
    return ct.startswith("image/") or fn.endswith(_IMAGE_EXTS)


def _save_composition_to_latest(composition: str) -> str:
    value = str(composition or "").strip()
    if not value:
        return ""
    rows = pose_core._load_index()
    if not rows:
        return ""
    rows[0]["composition_feature"] = value
    rows[0]["updated_at"] = datetime.now().astimezone().isoformat()
    pose_core._save_index(rows)
    return str(rows[0].get("id") or "")


def _save_composition_for_pose(wanted: str, composition: str) -> bool:
    value = str(composition or "").strip()
    if not value:
        return False
    rows = pose_core._load_index()
    row = next((r for r in rows if str(r.get("id") or "").upper() == wanted.upper()), None)
    if not row:
        return False
    row["composition_feature"] = value
    row["updated_at"] = datetime.now().astimezone().isoformat()
    pose_core._save_index(rows)
    return True


def _split_manual_composition(text: str):
    """Return (wanted, composition, cleaned_request) for manual /姿勢 修正.

    Composition is intentionally parsed here instead of core.py so the older Pose=
    parser cannot absorb `Composition=...` into pose_description.
    """
    m = re.match(r"^修正\s+(P\d+)\s+(.+)$", str(text or "").strip(), re.I | re.S)
    if not m:
        return None, "", text
    wanted, spec = m.group(1).upper(), m.group(2).strip()
    if spec in ("重新判讀", "重判", "Gemini"):
        return wanted, "", text

    cm = re.search(r"(?:^|\s)Composition\s*[=:：]\s*(.+?)\s*$", spec, re.I | re.S)
    if not cm:
        return wanted, "", text

    composition = cm.group(1).strip()
    cleaned_spec = spec[:cm.start()].strip()
    cleaned_request = f"修正 {wanted} {cleaned_spec}".strip()
    return wanted, composition, cleaned_request


async def _replace_reference(ctx: Any, wanted: str, attachment: Any) -> None:
    rows = pose_core._load_index()
    row = next((r for r in rows if str(r.get("id") or "").upper() == wanted), None)
    if not row:
        await ctx.reply(f"找不到 `{wanted}`。", mention_author=False)
        return

    old_path = str(row.get("file_path") or "")
    ext = os.path.splitext(str(getattr(attachment, "filename", "") or ""))[1].lower()
    if ext not in _IMAGE_EXTS:
        ext = os.path.splitext(old_path)[1].lower() if os.path.splitext(old_path)[1].lower() in _IMAGE_EXTS else ".jpg"
    new_path = pose_core._files_dir() / f"{wanted}{ext}"
    tmp_path = pose_core._files_dir() / f".{wanted}.replace{ext}"
    await attachment.save(str(tmp_path))
    os.replace(str(tmp_path), str(new_path))
    if old_path and old_path != str(new_path) and os.path.exists(old_path):
        try:
            os.remove(old_path)
        except Exception:
            pass

    row["file_path"] = str(new_path)
    row["mime_type"] = str(getattr(attachment, "content_type", "") or row.get("mime_type") or "image/jpeg")
    row["source"] = "original_reference"
    row["reference_replaced_at"] = datetime.now().astimezone().isoformat()
    row["updated_at"] = row["reference_replaced_at"]
    pose_core._save_index(rows)

    try:
        state = pose_core_app.load_state()
        pending = state.get(_STATE_KEY) if isinstance(state, dict) else None
        if isinstance(pending, dict) and str(pending.get("pose_id") or "").upper() == wanted:
            state[_STATE_KEY] = None
            pose_core_app.save_state(state)
    except Exception:
        pass

    await ctx.reply(
        f"🖼️ **{wanted} 姿勢參考圖已更換。**\n"
        "原有名稱、分類、標籤、Camera、Visible、Pose、Composition 均保留；沒有重新叫 Gemini 判讀。\n"
        f"下一次使用請再輸入 `/姿勢 穿 {wanted}`。",
        file=discord.File(str(new_path)), mention_author=False,
    )


pose_core_app: Any = None


def install_pose_library_composition_replace(app: Any) -> Dict[str, Any]:
    global pose_core_app
    pose_core_app = app

    original_analysis = getattr(app, "build_pose_reference_analysis", None)
    last_observation: Dict[str, str] = {"composition_feature": ""}

    async def analysis_with_composition(context):
        result = await original_analysis(context) if callable(original_analysis) else {}
        result = dict(result or {})
        comp = str(result.get("composition_feature") or "").strip()
        if comp:
            last_observation["composition_feature"] = comp

        try:
            state = app.load_state()
            pending = state.get(_STATE_KEY) if isinstance(state, dict) else None
            if isinstance(pending, dict) and str(pending.get("source") or "") == "pose_library":
                saved = str(pending.get("composition_feature") or "").strip()
                if saved:
                    result["composition_feature"] = saved
                    camera = str(result.get("camera_intent") or "").strip()
                    if "Composition emphasis:" not in camera:
                        result["camera_intent"] = (camera + f" Composition emphasis: {saved}").strip()
        except Exception:
            pass
        return result

    app.build_pose_reference_analysis = analysis_with_composition

    original_generate = getattr(app, "_generate_photo_from_context", None)
    if callable(original_generate):
        async def generate_with_composition_trace(context, msg=None):
            ctx = dict(context or {})
            try:
                state = app.load_state()
                pending = state.get(_STATE_KEY) if isinstance(state, dict) else None
                if isinstance(pending, dict) and str(pending.get("source") or "") == "pose_library":
                    comp = str(pending.get("composition_feature") or "").strip()
                    if comp:
                        ctx["pose_composition_feature"] = comp
                        print(f"🧭 [POSE_COMPOSITION_TO_TRACE] {comp}")
            except Exception as exc:
                print(f"⚠️ [POSE_COMPOSITION_TRACE_FAILED] {type(exc).__name__}: {exc}")
            return await original_generate(ctx, msg=msg)

        app._generate_photo_from_context = generate_with_composition_trace

    old_command = app.girlfriend_bot.get_command("姿勢")
    if old_command is None:
        raise RuntimeError("/姿勢 command not installed")
    try:
        app.girlfriend_bot.remove_command("姿勢")
    except Exception:
        pass

    @app.girlfriend_bot.command(name="姿勢")
    async def pose_command_v11306(ctx, *, request: str = ""):
        text = str(request or "").strip()
        attachments = [a for a in (getattr(getattr(ctx, "message", None), "attachments", []) or []) if _is_image_attachment(a)]

        replace_match = re.match(r"^修正\s+(P\d+)\s*$", text, re.I)
        if replace_match and attachments:
            await _replace_reference(ctx, replace_match.group(1).upper(), attachments[0])
            return

        is_add = bool(re.match(r"^新增(?:\s|$)", text))
        reread_match = re.match(r"^修正\s+(P\d+)\s+(重新判讀|重判|Gemini)\s*$", text, re.I)
        if is_add or reread_match:
            last_observation["composition_feature"] = ""

        manual_wanted, manual_composition, cleaned_text = _split_manual_composition(text)

        # If Composition is the only field, save it directly instead of invoking core
        # with an otherwise-empty 修正 command (which would only print usage help).
        if manual_wanted and manual_composition and cleaned_text.strip() == f"修正 {manual_wanted}":
            row = pose_core._find_pose(manual_wanted)
            if not row:
                await ctx.reply(f"找不到 `{manual_wanted}`。", mention_author=False)
                return
            _save_composition_for_pose(manual_wanted, manual_composition)
            await pose_core._show_pose(ctx, pose_core._find_pose(manual_wanted))
            await ctx.send(f"🧭 **Composition：** `{manual_composition}`")
            return

        await ctx.invoke(old_command, request=cleaned_text)

        if manual_wanted and manual_composition:
            if _save_composition_for_pose(manual_wanted, manual_composition):
                await ctx.send(f"🧭 **Composition：** `{manual_composition}`")
            return

        if is_add:
            comp = str(last_observation.get("composition_feature") or "").strip()
            pose_id = _save_composition_to_latest(comp)
            if pose_id and comp:
                await ctx.send(f"🧭 **Composition：** `{comp}`")
            return

        if reread_match:
            wanted = reread_match.group(1).upper()
            row = pose_core._find_pose(wanted)
            comp = str((row or {}).get("composition_feature") or "").strip()
            if comp:
                await ctx.send(f"🧭 **Composition：** `{comp}`")
            else:
                await ctx.send("🧭 **Composition：** `—`")
            return

        wear_match = re.match(r"^穿\s+(P\d+)\s*$", text, re.I)
        if wear_match:
            wanted = wear_match.group(1).upper()
            row = pose_core._find_pose(wanted)
            comp = str((row or {}).get("composition_feature") or "").strip()
            state = app.load_state()
            pending = state.get(_STATE_KEY) if isinstance(state, dict) else None
            if isinstance(pending, dict) and str(pending.get("pose_id") or "").upper() == wanted:
                pending["composition_feature"] = comp
                state[_STATE_KEY] = pending
                app.save_state(state)
            return

        look_match = re.match(r"^看\s+(P\d+)\s*$", text, re.I)
        if look_match:
            row = pose_core._find_pose(look_match.group(1))
            comp = str((row or {}).get("composition_feature") or "").strip()
            await ctx.send(f"🧭 **Composition：** `{comp or '—'}`")

    return {
        "version": VERSION,
        "composition": "Gemini observed + persisted + visible + reusable + manual Composition parser",
        "trace_field": "pose_composition_feature",
        "replace_reference": "/姿勢 修正 Pxxx + image; metadata preserved; no Gemini rerun",
    }
