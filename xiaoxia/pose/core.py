# -*- coding: utf-8 -*-
"""Pose Library v1.14.00 — consolidated original-reference asset library.

One module owns the Pose Library lifecycle: storage, Gemini observer metadata,
manual edits, reference replacement, browsing/pagination, and pending selection.

Design rule:
- Figure 9 carries fine geometry.
- Camera records photographer position/view direction.
- Composition records camera-relative depth/visual flow.
- Pose records only discriminative actions; never a joint-by-joint anatomy spec.
"""
from __future__ import annotations

import json
import math
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import discord

POSE_VERSION = "1.14.00"
_STATE_KEY = "photo_pending_pose_reference"
_IMAGE_EXTS = (".jpg", ".jpeg", ".png", ".webp")
PAGE_SIZE = 10


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
    nums = []
    for row in rows:
        m = re.match(r"^P(\d+)$", str(row.get("id") or "").strip().upper())
        if m:
            nums.append(int(m.group(1)))
    return f"P{(max(nums) if nums else 0) + 1:03d}"


def _find_pose(pose_id: str) -> Optional[Dict[str, Any]]:
    wanted = str(pose_id or "").strip().upper()
    return next((r for r in _load_index() if str(r.get("id") or "").strip().upper() == wanted), None)


def _is_image_attachment(a: Any) -> bool:
    ct = str(getattr(a, "content_type", "") or "").lower()
    fn = str(getattr(a, "filename", "") or "").lower()
    return ct.startswith("image/") or fn.endswith(_IMAGE_EXTS)


def _category_from_analysis(scope: str, desc: str) -> str:
    text = f"{scope} {desc}".lower()
    if any(x in text for x in ("prone", "supine", "side-lying", "side lying", "lying", "reclining", "lies", "laying")):
        return "趴／躺姿"
    if any(x in text for x in ("kneeling", "kneels", "on both knees", "crouching", "crouched", "squatting", "squat")):
        return "蹲／跪姿"
    if any(x in text for x in ("sitting", "seated", "sits")):
        return "坐姿"
    if any(x in text for x in ("standing", "stands", "stood", "walking", "walks")):
        return "站／走姿"
    if any(x in text for x in ("leaning against", "leans against", "supported against", "lean against")):
        return "倚靠"
    return "其他"


def _name_from_analysis(category: str, camera: str, desc: str) -> str:
    blob = f"{camera} {desc}".lower()
    bits = [category]
    if any(x in blob for x in ("looking back", "turned back", "turning back")):
        bits.append("回頭")
    if "full-body" in blob or "full body" in blob:
        bits.append("全身")
    if "rear three-quarter" in blob:
        bits.append("後3/4")
    return "・".join(dict.fromkeys(bits))[:80]


def _tags_from_analysis(category: str, camera: str, scope: str, desc: str) -> List[str]:
    blob = f"{camera} {scope} {desc}".lower()
    tags = [category]
    mapping = [
        ("全身", ("full-body", "full body")),
        ("回頭", ("looking back", "turned back", "turning back")),
        ("後3/4", ("rear three-quarter",)),
        ("俯拍", ("elevated", "high-angle", "high angle", "from above")),
        ("仰拍", ("low-angle", "low angle", "from below")),
        ("托臉", ("supporting the cheek", "supporting cheek", "hand on cheek")),
        ("扶欄", ("hand on the rail", "hand on railing")),
    ]
    for label, needles in mapping:
        if any(n in blob for n in needles) and label not in tags:
            tags.append(label)
    return tags[:8]


async def _analyze(app: Any, url: str, mime: str) -> Dict[str, str]:
    builder = getattr(app, "build_pose_reference_analysis", None)
    if not callable(builder):
        return {}
    try:
        return dict(await builder({"pose_reference_url": url, "pose_reference_mime_type": mime}) or {})
    except Exception as exc:
        print(f"⚠️ [POSE_LIBRARY_ANALYSIS_FAILED] {type(exc).__name__}: {exc}")
        return {}


def _normalize_analysis(data: Dict[str, Any]) -> Dict[str, str]:
    return {
        "camera_intent": str(data.get("camera_intent") or "").strip(),
        "visible_pose_scope": str(data.get("visible_pose_scope") or "").strip(),
        "pose_description": str(data.get("pose_description") or "").strip(),
        "composition_feature": str(data.get("composition_feature") or "").strip(),
    }


async def _add_pose(app: Any, attachment: discord.Attachment, note: str = "") -> Dict[str, Any]:
    rows = _load_index()
    pose_id = _next_pose_id(rows)
    ext = os.path.splitext(str(getattr(attachment, "filename", "") or ""))[1].lower()
    if ext not in _IMAGE_EXTS:
        ext = ".jpg"
    path = _files_dir() / f"{pose_id}{ext}"
    await attachment.save(str(path))
    mime = str(getattr(attachment, "content_type", "") or "image/jpeg")
    analysis = _normalize_analysis(await _analyze(app, str(getattr(attachment, "url", "") or ""), mime))
    category = _category_from_analysis(analysis["visible_pose_scope"], analysis["pose_description"])
    now = datetime.now().astimezone().isoformat()
    row = {
        "id": pose_id,
        "name": str(note or "").strip()[:80] or _name_from_analysis(category, analysis["camera_intent"], analysis["pose_description"]),
        "category": category,
        "tags": _tags_from_analysis(category, analysis["camera_intent"], analysis["visible_pose_scope"], analysis["pose_description"]),
        "file_path": str(path),
        "mime_type": mime,
        **analysis,
        "source": "original_reference",
        "metadata_version": POSE_VERSION,
        "created_at": now,
        "updated_at": now,
    }
    rows.insert(0, row)
    _save_index(rows)
    return row


async def _reread_pose(app: Any, wanted: str) -> Optional[Dict[str, Any]]:
    rows = _load_index()
    row = next((r for r in rows if str(r.get("id") or "").upper() == wanted), None)
    if not row:
        return None
    path = str(row.get("file_path") or "")
    if not path or not os.path.exists(path):
        return row
    url = await app._seedream_upload_single_file(path)
    analysis = _normalize_analysis(await _analyze(app, url, str(row.get("mime_type") or "image/jpeg")))
    row.update(analysis)
    row["category"] = _category_from_analysis(analysis["visible_pose_scope"], analysis["pose_description"])
    row["tags"] = _tags_from_analysis(row["category"], analysis["camera_intent"], analysis["visible_pose_scope"], analysis["pose_description"])
    row["metadata_version"] = POSE_VERSION
    row["updated_at"] = datetime.now().astimezone().isoformat()
    _save_index(rows)
    return row


async def _replace_reference(app: Any, wanted: str, attachment: Any) -> Optional[Dict[str, Any]]:
    rows = _load_index()
    row = next((r for r in rows if str(r.get("id") or "").upper() == wanted), None)
    if not row:
        return None
    old_path = str(row.get("file_path") or "")
    ext = os.path.splitext(str(getattr(attachment, "filename", "") or ""))[1].lower()
    if ext not in _IMAGE_EXTS:
        ext = os.path.splitext(old_path)[1].lower() if os.path.splitext(old_path)[1].lower() in _IMAGE_EXTS else ".jpg"
    new_path = _files_dir() / f"{wanted}{ext}"
    tmp = _files_dir() / f".{wanted}.replace{ext}"
    await attachment.save(str(tmp))
    os.replace(str(tmp), str(new_path))
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
    _save_index(rows)
    state = app.load_state()
    pending = state.get(_STATE_KEY) if isinstance(state, dict) else None
    if isinstance(pending, dict) and str(pending.get("pose_id") or "").upper() == wanted:
        state[_STATE_KEY] = None
        app.save_state(state)
    return row


_FIELD_ALIASES = {
    "名稱": "name", "分類": "category", "標籤": "tags",
    "camera": "camera_intent", "visible": "visible_pose_scope",
    "pose": "pose_description", "composition": "composition_feature",
}


def _apply_field_updates(row: Dict[str, Any], spec: str) -> bool:
    names = "|".join(re.escape(x) for x in ("名稱", "分類", "標籤", "Camera", "Visible", "Pose", "Composition"))
    pattern = re.compile(rf"(?:^|\s)({names})\s*[=:：]\s*(.+?)(?=\s+(?:{names})\s*[=:：]|$)", re.I | re.S)
    changed = False
    for match in pattern.finditer(str(spec or "")):
        label = match.group(1)
        key = _FIELD_ALIASES.get(label.lower(), _FIELD_ALIASES.get(label))
        if not key:
            continue
        value = match.group(2).strip()
        row[key] = [x.strip() for x in re.split(r"[,，、]+", value) if x.strip()] if key == "tags" else value
        changed = True
    return changed


def _pose_text(row: Dict[str, Any]) -> str:
    return (
        f"💃 **{row.get('id')}｜{row.get('name') or '姿勢'}**\n"
        f"分類：{row.get('category') or '其他'}\n"
        f"標籤：{'、'.join(row.get('tags') or []) or '—'}\n"
        f"Camera：`{row.get('camera_intent') or '—'}`\n"
        f"Visible：`{row.get('visible_pose_scope') or '—'}`\n"
        f"Pose：`{row.get('pose_description') or '—'}`\n"
        f"🧭 Composition：`{row.get('composition_feature') or '—'}`"
    )


async def _show_pose(ctx: Any, row: Dict[str, Any]) -> None:
    path = str(row.get("file_path") or "")
    if path and os.path.exists(path):
        await ctx.reply(_pose_text(row), file=discord.File(path), mention_author=False)
    else:
        await ctx.reply(_pose_text(row) + "\n⚠️ 原始姿勢圖檔不存在。", mention_author=False)


def _page_payload(rows: List[Dict[str, Any]], page: int) -> Tuple[str, List[discord.Embed], List[discord.File], int, int]:
    pages = max(1, math.ceil(len(rows) / PAGE_SIZE))
    page = max(1, min(page, pages))
    shown = rows[(page - 1) * PAGE_SIZE: page * PAGE_SIZE]
    embeds, files = [], []
    for i, row in enumerate(shown):
        path = str(row.get("file_path") or "")
        ext = os.path.splitext(path)[1] or ".jpg"
        filename = f"pose_p{page}_{i}{ext}"
        emb = discord.Embed(title=f"{row.get('id')}｜{row.get('name') or '姿勢'}", description=f"{row.get('category') or '其他'}｜{'、'.join(row.get('tags') or [])}")
        if path and os.path.exists(path):
            files.append(discord.File(path, filename=filename))
            emb.set_thumbnail(url=f"attachment://{filename}")
        embeds.append(emb)
    return f"💃 **小俠姿勢櫃**｜共 {len(rows)} 張｜第 {page}/{pages} 頁", embeds, files, page, pages


class PosePager(discord.ui.View):
    def __init__(self, rows: List[Dict[str, Any]], page: int, owner_id: int | None = None):
        super().__init__(timeout=600)
        self.rows, self.page, self.owner_id = rows, page, owner_id
        self.pages = max(1, math.ceil(len(rows) / PAGE_SIZE))
        self._sync()

    def _sync(self):
        self.prev_button.disabled = self.page <= 1
        self.next_button.disabled = self.page >= self.pages

    async def _render(self, interaction: discord.Interaction, page: int):
        if self.owner_id is not None and getattr(getattr(interaction, "user", None), "id", None) != self.owner_id:
            await interaction.response.send_message("這是大俠目前開啟的姿勢櫃頁面。", ephemeral=True)
            return
        await interaction.response.defer()
        content, embeds, files, self.page, self.pages = _page_payload(self.rows, page)
        self._sync()
        await interaction.message.edit(content=content, embeds=embeds, attachments=files, view=self)

    @discord.ui.button(label="上一頁", emoji="◀️", style=discord.ButtonStyle.secondary)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._render(interaction, self.page - 1)

    @discord.ui.button(label="下一頁", emoji="▶️", style=discord.ButtonStyle.primary)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._render(interaction, self.page + 1)


def load_pose_library() -> List[Dict[str, Any]]:
    return _load_index()


def pose_reference_for_generation(pose_id: str) -> Optional[str]:
    row = _find_pose(pose_id)
    path = str((row or {}).get("file_path") or "")
    return path if path and os.path.exists(path) else None


def install_pose_commands(app: Any) -> Dict[str, Any]:
    bot = getattr(app, "girlfriend_bot", None)
    if bot is None:
        raise RuntimeError("girlfriend_bot not found")
    for name in ("姿勢", "姿勢庫"):
        try:
            bot.remove_command(name)
        except Exception:
            pass

    @bot.command(name="姿勢")
    async def pose_command(ctx, *, request: str = ""):
        text = str(request or "").strip()
        attachments = [a for a in (getattr(getattr(ctx, "message", None), "attachments", []) or []) if _is_image_attachment(a)]

        page = 1 if not text else None
        if text:
            m = re.match(r"^(?:第\s*)?(\d+)\s*(?:頁)?$", text)
            if m:
                page = int(m.group(1))
        if page is not None:
            rows = _load_index()
            if not rows:
                await ctx.reply("💃 姿勢櫃目前是空的。附上一張姿勢圖後輸入 `/姿勢 新增` 即可收錄。", mention_author=False)
                return
            content, embeds, files, page, _ = _page_payload(rows, page)
            await ctx.reply(content, embeds=embeds, files=files, view=PosePager(rows, page, getattr(getattr(ctx, "author", None), "id", None)), mention_author=False)
            return

        m = re.match(r"^看\s+(P\d+)\s*$", text, re.I)
        if m:
            row = _find_pose(m.group(1))
            if not row:
                await ctx.reply(f"找不到 `{m.group(1).upper()}`。", mention_author=False)
                return
            await _show_pose(ctx, row)
            return

        m = re.match(r"^穿\s+(P\d+)\s*$", text, re.I)
        if m:
            row = _find_pose(m.group(1))
            if not row:
                await ctx.reply(f"找不到 `{m.group(1).upper()}`。", mention_author=False)
                return
            path = str(row.get("file_path") or "")
            if not path or not os.path.exists(path):
                await ctx.reply("⚠️ 這個姿勢的原始圖檔不存在。", mention_author=False)
                return
            url = await app._seedream_upload_single_file(path)
            state = app.load_state()
            state[_STATE_KEY] = {
                "url": url,
                "content_type": row.get("mime_type") or "image/jpeg",
                "pose_id": row.get("id"),
                "camera_intent": row.get("camera_intent") or "",
                "visible_pose_scope": row.get("visible_pose_scope") or "",
                "pose_description": row.get("pose_description") or "",
                "composition_feature": row.get("composition_feature") or "",
                "source": "pose_library",
            }
            app.save_state(state)
            await ctx.reply(f"💃 已穿上 **{row.get('id')}｜{row.get('name')}**。下一張 `/photo` 會使用這個姿勢。", mention_author=False)
            return

        if re.match(r"^新增(?:\s|$)", text):
            if not attachments:
                await ctx.reply("請附上一張原始 Pose Reference，再輸入 `/姿勢 新增`。", mention_author=False)
                return
            note = re.sub(r"^新增\s*", "", text).strip()
            status = await ctx.reply("🔎 正在保存原始姿勢圖並建立 Camera / Visible / Pose / Composition…", mention_author=False)
            try:
                row = await _add_pose(app, attachments[0], note)
                await status.delete()
                await _show_pose(ctx, row)
            except Exception as exc:
                await status.edit(content=f"⚠️ 姿勢新增失敗：`{type(exc).__name__}: {str(exc)[:900]}`")
            return

        m = re.match(r"^修正\s+(P\d+)\s*(.*)$", text, re.I | re.S)
        if m:
            wanted, spec = m.group(1).upper(), m.group(2).strip()
            row = _find_pose(wanted)
            if not row:
                await ctx.reply(f"找不到 `{wanted}`。", mention_author=False)
                return
            if attachments and not spec:
                updated = await _replace_reference(app, wanted, attachments[0])
                await ctx.reply(f"🖼️ **{wanted} 姿勢參考圖已更換。** Metadata 保留，沒有重新判讀。", file=discord.File(str(updated.get("file_path"))), mention_author=False)
                return
            if spec in ("重新判讀", "重判", "Gemini"):
                updated = await _reread_pose(app, wanted)
                await _show_pose(ctx, updated)
                return
            rows = _load_index()
            target = next((r for r in rows if str(r.get("id") or "").upper() == wanted), None)
            if not spec or not _apply_field_updates(target, spec):
                await ctx.reply("用法：`/姿勢 修正 P001 名稱=... 分類=... 標籤=... Camera=... Visible=... Pose=... Composition=...`，或 `/姿勢 修正 P001 重新判讀`。", mention_author=False)
                return
            target["metadata_version"] = POSE_VERSION
            target["updated_at"] = datetime.now().astimezone().isoformat()
            _save_index(rows)
            await _show_pose(ctx, target)
            return

        m = re.match(r"^刪除\s+(P\d+)\s*$", text, re.I)
        if m:
            wanted = m.group(1).upper()
            rows = _load_index()
            row = next((r for r in rows if str(r.get("id") or "").upper() == wanted), None)
            if not row:
                await ctx.reply(f"找不到 `{wanted}`。", mention_author=False)
                return
            try:
                os.remove(str(row.get("file_path") or ""))
            except Exception:
                pass
            _save_index([r for r in rows if str(r.get("id") or "").upper() != wanted])
            state = app.load_state()
            pending = state.get(_STATE_KEY) if isinstance(state, dict) else None
            if isinstance(pending, dict) and str(pending.get("pose_id") or "").upper() == wanted:
                state[_STATE_KEY] = None
                app.save_state(state)
            await ctx.reply(f"🗑️ `{wanted}` 已從姿勢櫃刪除。", mention_author=False)
            return

        await ctx.reply("💃 用法：`/姿勢`、`/姿勢 看 P001`、`/姿勢 穿 P001`、附圖 `/姿勢 新增`、`/姿勢 修正 P001 ...`、`/姿勢 刪除 P001`。", mention_author=False)

    @bot.command(name="姿勢庫", hidden=True)
    async def pose_library_alias(ctx, *, request: str = ""):
        command = bot.get_command("姿勢")
        if command:
            await ctx.invoke(command, request=request)

    app.pose_reference_for_generation = pose_reference_for_generation
    app.load_pose_library = load_pose_library
    return {
        "version": POSE_VERSION,
        "commands": ["/姿勢", "看", "穿", "新增", "修正", "刪除"],
        "metadata": ["Camera", "Visible", "Pose", "Composition"],
        "pagination": True,
        "asset": "original_pose_reference",
    }
