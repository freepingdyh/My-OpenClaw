# -*- coding: utf-8 -*-
"""Pose Library v1.13.00 — original-reference asset library.

Pxxx stores the ORIGINAL pose reference plus Gemini observational metadata.
It never converts the source person into Xiaoxia during library ingestion.
Command vocabulary intentionally mirrors Wardrobe: /姿勢, 看, 穿, 新增, 修正, 刪除.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import discord

POSE_VERSION = "1.13.00"
_STATE_KEY = "photo_pending_pose_reference"
_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def _root_dir() -> Path:
    p = Path(os.environ.get("XIAOXIA_POSE_LIBRARY_DIR") or "/data/memory/pose_library")
    p.mkdir(parents=True, exist_ok=True)
    return p


def _files_dir() -> Path:
    p = _root_dir() / "files"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _index_path() -> Path:
    return _root_dir() / "index.json"


def _load_index() -> List[Dict[str, Any]]:
    try:
        data = json.loads(_index_path().read_text(encoding="utf-8"))
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _save_index(rows: List[Dict[str, Any]]) -> None:
    _index_path().write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def _next_pose_id(rows: List[Dict[str, Any]]) -> str:
    n = 0
    for row in rows:
        m = re.match(r"^P(\d+)$", str(row.get("id") or "").strip().upper())
        if m:
            n = max(n, int(m.group(1)))
    return f"P{n + 1:03d}"


def _find_pose(pose_id: str) -> Optional[Dict[str, Any]]:
    wanted = str(pose_id or "").strip().upper()
    return next((r for r in _load_index() if str(r.get("id") or "").upper() == wanted), None)


def _is_image_attachment(a: Any) -> bool:
    ct = str(getattr(a, "content_type", "") or "").lower()
    fn = str(getattr(a, "filename", "") or "").lower()
    return ct.startswith("image/") or fn.endswith(_IMAGE_EXTS)


def _category_from_analysis(scope: str, desc: str) -> str:
    text = f"{scope} {desc}".lower()
    if any(x in text for x in ("lying", "reclining", "lying down")): return "躺姿"
    if any(x in text for x in ("kneeling", "crouch", "squat")): return "蹲／跪姿"
    if any(x in text for x in ("sitting", "seated")): return "坐姿"
    if any(x in text for x in ("leaning", "lean against")): return "倚靠"
    if any(x in text for x in ("standing", "stands")): return "站姿"
    return "其他"


def _name_from_analysis(category: str, camera: str, desc: str) -> str:
    # Human-facing name stays Chinese/simple; raw Gemini English remains metadata only.
    camera_l = camera.lower()
    bits = [category]
    if "high-angle" in camera_l or "high angle" in camera_l or "from above" in camera_l: bits.append("俯拍")
    elif "low-angle" in camera_l or "low angle" in camera_l or "from below" in camera_l: bits.append("仰拍")
    if "full body" in camera_l: bits.append("全身")
    elif "three-quarter" in camera_l or "3/4" in camera_l: bits.append("3/4身")
    elif "close-up" in camera_l or "close up" in camera_l: bits.append("特寫")
    return "・".join(dict.fromkeys(bits))[:80]


def _tags_from_analysis(category: str, camera: str, scope: str, desc: str) -> List[str]:
    tags = [category]
    blob = f"{camera} {scope} {desc}".lower()
    mapping = [
        ("俯拍", ("high-angle", "high angle", "from above")),
        ("仰拍", ("low-angle", "low angle", "from below")),
        ("全身", ("full body",)), ("3/4身", ("three-quarter", "3/4")),
        ("特寫", ("close-up", "close up")), ("回頭", ("looking back", "looks back")),
        ("雙手", ("both hands",)), ("交叉腿", ("crossed legs", "legs crossed")),
    ]
    for label, needles in mapping:
        if any(n in blob for n in needles) and label not in tags: tags.append(label)
    return tags[:8]


async def _analyze(app: Any, url: str, mime: str) -> Dict[str, str]:
    builder = getattr(app, "build_pose_reference_analysis", None)
    if not callable(builder):
        return {"camera_intent": "", "visible_pose_scope": "", "pose_description": ""}
    try:
        return await builder({"pose_reference_url": url, "pose_reference_mime_type": mime}) or {}
    except Exception as exc:
        print(f"⚠️ [POSE_LIBRARY_ANALYSIS_FAILED] {type(exc).__name__}: {exc}")
        return {"camera_intent": "", "visible_pose_scope": "", "pose_description": ""}


async def _add_pose(app: Any, attachment: discord.Attachment, note: str = "") -> Dict[str, Any]:
    rows = _load_index()
    pose_id = _next_pose_id(rows)
    ext = os.path.splitext(str(getattr(attachment, "filename", "") or ""))[1].lower()
    if ext not in _IMAGE_EXTS: ext = ".jpg"
    final_path = _files_dir() / f"{pose_id}{ext}"
    await attachment.save(str(final_path))
    mime = str(getattr(attachment, "content_type", "") or "image/jpeg")
    analysis = await _analyze(app, str(getattr(attachment, "url", "") or ""), mime)
    camera = str(analysis.get("camera_intent") or "").strip()
    scope = str(analysis.get("visible_pose_scope") or "").strip()
    desc = str(analysis.get("pose_description") or "").strip()
    category = _category_from_analysis(scope, desc)
    row = {
        "id": pose_id,
        "name": str(note or "").strip()[:80] or _name_from_analysis(category, camera, desc),
        "category": category,
        "tags": _tags_from_analysis(category, camera, scope, desc),
        "file_path": str(final_path),
        "mime_type": mime,
        "camera_intent": camera,
        "visible_pose_scope": scope,
        "pose_description": desc,
        "source": "original_reference",
        "created_at": datetime.now().astimezone().isoformat(),
    }
    rows.insert(0, row)
    _save_index(rows)
    print(f"✅ [POSE_LIBRARY_ADDED] id={pose_id} category={category} original_reference=True")
    return row


def load_pose_library() -> List[Dict[str, Any]]:
    return _load_index()


def pose_reference_for_generation(pose_id: str) -> Optional[str]:
    row = _find_pose(pose_id)
    path = str((row or {}).get("file_path") or "")
    return path if path and os.path.exists(path) else None


async def _show_pose(ctx: Any, row: Dict[str, Any]) -> None:
    path = str(row.get("file_path") or "")
    text = (
        f"💃 **{row.get('id')}｜{row.get('name') or '姿勢'}**\n"
        f"分類：{row.get('category') or '其他'}\n"
        f"標籤：{'、'.join(row.get('tags') or []) or '—'}\n"
        f"Camera：`{row.get('camera_intent') or '—'}`\n"
        f"Visible：`{row.get('visible_pose_scope') or '—'}`\n"
        f"Pose：`{row.get('pose_description') or '—'}`"
    )
    if path and os.path.exists(path):
        await ctx.reply(text, file=discord.File(path), mention_author=False)
    else:
        await ctx.reply(text + "\n⚠️ 原始姿勢圖檔不存在。", mention_author=False)


async def _list_poses(ctx: Any, rows: List[Dict[str, Any]]) -> None:
    if not rows:
        await ctx.reply("💃 姿勢櫃目前是空的。附上一張姿勢圖後輸入 `/姿勢 新增` 即可收錄。", mention_author=False)
        return
    # Discord permits at most 10 attachments per message. Show newest 10 with thumbnails;
    # the textual index still reports total count.
    shown = rows[:10]
    files, embeds = [], []
    for i, row in enumerate(shown):
        path = str(row.get("file_path") or "")
        filename = f"pose_{i}{os.path.splitext(path)[1] or '.jpg'}"
        emb = discord.Embed(title=f"{row.get('id')}｜{row.get('name') or '姿勢'}", description=f"{row.get('category') or '其他'}｜{'、'.join(row.get('tags') or [])}")
        if path and os.path.exists(path):
            files.append(discord.File(path, filename=filename))
            emb.set_thumbnail(url=f"attachment://{filename}")
        embeds.append(emb)
    suffix = "" if len(rows) <= 10 else f"\n目前先顯示最新 10 張；共 {len(rows)} 張。"
    await ctx.reply(f"💃 **小俠姿勢櫃**｜共 {len(rows)} 張{suffix}", embeds=embeds, files=files, mention_author=False)


def _apply_field_updates(row: Dict[str, Any], spec: str) -> bool:
    changed = False
    aliases = {"名稱": "name", "分類": "category", "標籤": "tags", "camera": "camera_intent", "Camera": "camera_intent", "visible": "visible_pose_scope", "Visible": "visible_pose_scope", "pose": "pose_description", "Pose": "pose_description"}
    for key_cn, key in aliases.items():
        m = re.search(rf"(?:^|\s){re.escape(key_cn)}\s*[=:：]\s*(.+?)(?=\s+(?:名稱|分類|標籤|camera|Camera|visible|Visible|pose|Pose)\s*[=:：]|$)", spec)
        if not m: continue
        value = m.group(1).strip()
        row[key] = [x.strip() for x in re.split(r"[,，、]+", value) if x.strip()] if key == "tags" else value
        changed = True
    return changed


def install_pose_commands(app: Any) -> Dict[str, Any]:
    bot = getattr(app, "girlfriend_bot", None)
    if bot is None: raise RuntimeError("girlfriend_bot not found")
    for name in ("姿勢", "姿勢庫"):
        try: bot.remove_command(name)
        except Exception: pass

    @bot.command(name="姿勢")
    async def pose_command(ctx, *, request: str = ""):
        text = str(request or "").strip()
        attachments = [a for a in (getattr(getattr(ctx, "message", None), "attachments", []) or []) if _is_image_attachment(a)]

        if not text:
            await _list_poses(ctx, _load_index())
            return

        m = re.match(r"^看\s+(P\d+)\s*$", text, re.I)
        if m:
            row = _find_pose(m.group(1))
            if not row: await ctx.reply(f"找不到 `{m.group(1).upper()}`。", mention_author=False); return
            await _show_pose(ctx, row); return

        m = re.match(r"^穿\s+(P\d+)\s*$", text, re.I)
        if m:
            row = _find_pose(m.group(1))
            if not row: await ctx.reply(f"找不到 `{m.group(1).upper()}`。", mention_author=False); return
            path = str(row.get("file_path") or "")
            if not path or not os.path.exists(path): await ctx.reply("⚠️ 這個姿勢的原始圖檔不存在。", mention_author=False); return
            try:
                pose_url = await app._seedream_upload_single_file(path)
            except Exception as exc:
                await ctx.reply(f"⚠️ 姿勢圖上傳失敗：`{type(exc).__name__}: {str(exc)[:500]}`", mention_author=False); return
            state = app.load_state()
            state[_STATE_KEY] = {
                "url": pose_url, "content_type": row.get("mime_type") or "image/jpeg", "pose_id": row.get("id"),
                "camera_intent": row.get("camera_intent") or "", "visible_pose_scope": row.get("visible_pose_scope") or "",
                "pose_description": row.get("pose_description") or "", "source": "pose_library",
            }
            app.save_state(state)
            await ctx.reply(f"💃 已穿上 **{row.get('id')}｜{row.get('name')}**。下一張 `/photo` 會使用這個姿勢。", mention_author=False)
            return

        if re.match(r"^新增(?:\s|$)", text):
            if not attachments:
                await ctx.reply("請附上一張原始 Pose Reference，再輸入 `/姿勢 新增`。不會換人、不會改衣服、不會改背景。", mention_author=False); return
            note = re.sub(r"^新增\s*", "", text).strip()
            status = await ctx.reply("🔎 正在保存原始姿勢圖並讓 Gemini 建立姿勢／鏡位 metadata…", mention_author=False)
            try:
                row = await _add_pose(app, attachments[0], note)
                await status.delete()
                await _show_pose(ctx, row)
            except Exception as exc:
                await status.edit(content=f"⚠️ 姿勢新增失敗：`{type(exc).__name__}: {str(exc)[:900]}`")
            return

        m = re.match(r"^修正\s+(P\d+)\s*(.*)$", text, re.I)
        if m:
            wanted, spec = m.group(1).upper(), m.group(2).strip()
            rows = _load_index(); row = next((r for r in rows if str(r.get("id") or "").upper() == wanted), None)
            if not row: await ctx.reply(f"找不到 `{wanted}`。", mention_author=False); return
            if spec in ("重新判讀", "重判", "Gemini"):
                path = str(row.get("file_path") or "")
                if not path or not os.path.exists(path): await ctx.reply("⚠️ 原始姿勢圖不存在。", mention_author=False); return
                url = await app._seedream_upload_single_file(path)
                analysis = await _analyze(app, url, row.get("mime_type") or "image/jpeg")
                row.update(analysis)
                row["category"] = _category_from_analysis(row.get("visible_pose_scope", ""), row.get("pose_description", ""))
                row["tags"] = _tags_from_analysis(row["category"], row.get("camera_intent", ""), row.get("visible_pose_scope", ""), row.get("pose_description", ""))
            elif not spec or not _apply_field_updates(row, spec):
                await ctx.reply("用法：`/姿勢 修正 P001 名稱=... 分類=... 標籤=...`，或 `/姿勢 修正 P001 重新判讀`。", mention_author=False); return
            row["updated_at"] = datetime.now().astimezone().isoformat(); _save_index(rows)
            await _show_pose(ctx, row); return

        m = re.match(r"^刪除\s+(P\d+)\s*$", text, re.I)
        if m:
            wanted = m.group(1).upper(); rows = _load_index(); row = next((r for r in rows if str(r.get("id") or "").upper() == wanted), None)
            if not row: await ctx.reply(f"找不到 `{wanted}`。", mention_author=False); return
            try: os.remove(str(row.get("file_path") or ""))
            except Exception: pass
            _save_index([r for r in rows if str(r.get("id") or "").upper() != wanted])
            state = app.load_state(); pending = state.get(_STATE_KEY)
            if isinstance(pending, dict) and str(pending.get("pose_id") or "").upper() == wanted:
                state[_STATE_KEY] = None; app.save_state(state)
            await ctx.reply(f"🗑️ `{wanted}` 已從姿勢櫃刪除。", mention_author=False); return

        await ctx.reply("💃 用法：`/姿勢`、`/姿勢 看 P001`、`/姿勢 穿 P001`、附圖 `/姿勢 新增`、`/姿勢 修正 P001 ...`、`/姿勢 刪除 P001`。", mention_author=False)

    # Temporary alias for old muscle memory; all UI/docs use /姿勢.
    @bot.command(name="姿勢庫", hidden=True)
    async def pose_library_alias(ctx, *, request: str = ""):
        command = bot.get_command("姿勢")
        if command:
            await ctx.invoke(command, request=request)

    app.pose_reference_for_generation = pose_reference_for_generation
    app.load_pose_library = load_pose_library
    return {"version": POSE_VERSION, "commands": ["/姿勢", "看", "穿", "新增", "修正", "刪除"], "asset": "original_pose_reference", "gemini_metadata": True}
