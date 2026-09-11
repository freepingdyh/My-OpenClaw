# -*- coding: utf-8 -*-
"""Xiaoxia Pose Library: candidate review flow + Seedream v5 repair."""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
import discord

MODEL_ID = "fal-ai/bytedance/seedream/v4.5/edit"
REPAIR_MODEL_ID = os.environ.get("XIAOXIA_POSE_REPAIR_MODEL") or "bytedance/seedream/v5/pro/edit"
POSE_VERSION = "1.12.06an"


def _env_bool(name: str, default: bool = True) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return bool(default)
    return str(raw).strip().lower() not in {"0", "false", "no", "off"}


def _root_dir() -> Path:
    return Path(os.environ.get("XIAOXIA_POSE_LIBRARY_DIR") or "/data/memory/pose_library")


def _files_dir() -> Path:
    p = _root_dir() / "files"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _candidate_dir() -> Path:
    p = _root_dir() / "candidates"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _index_path() -> Path:
    _root_dir().mkdir(parents=True, exist_ok=True)
    return _root_dir() / "index.json"


def _load_index() -> List[Dict[str, Any]]:
    p = _index_path()
    if not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
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


def _identity_paths() -> List[str]:
    raw = str(os.environ.get("XIAOXIA_POSE_IDENTITY_REFS") or "").strip()
    if raw:
        candidates = [x.strip() for x in re.split(r"[;,\n]+", raw) if x.strip()]
    else:
        candidates = [f"dataset/Xiaoxia_{i:03d}.png" for i in range(1, 10)]
    existing = [p for p in candidates if os.path.exists(p)]
    if len(existing) < 9:
        raise RuntimeError(f"POSE_IDENTITY_REFS_NEED_9: found={len(existing)}")
    return existing[:9]


def _xiaoxia_identity_block() -> str:
    return (
        "Figures 1-9 are canonical identity references for the same adult woman, Xiaoxia. "
        "Preserve her face identity, facial proportions, fair skin, tall slender long-limbed build, "
        "long brown slightly wavy hair with airy bangs, defined waist and natural body proportions. "
        "Do not average her identity with the pose-reference person. Identity has highest priority."
    )


def _standard_pose_asset_block() -> str:
    return (
        "Create a reusable pose-library asset rather than a finished lifestyle photo. "
        "Use a fitted plain white sleeveless top and plain white shorts, no logos, jewelry or hat. "
        "Use a clean neutral light-gray studio unless a bed/chair/sofa/floor support is physically required. "
        "Keep the whole pose readable and anatomically natural."
    )


def _build_prompt(user_text: str, has_pose_reference: bool) -> str:
    request = str(user_text or "").strip()
    if has_pose_reference:
        pose_rule = (
            "Figure 10 is POSE REFERENCE ONLY. Match it closely: body pose, pelvis and torso direction, "
            "spine lean, limb placement, joint angles, hand support points, head turn, weight distribution, "
            "camera side, camera height and framing. Do NOT copy Figure 10's face, hair, body identity, "
            "clothes, skin tone or accessories. Recreate the same pose with Xiaoxia from Figures 1-9."
        )
        if request:
            pose_rule += f" Additional pose guidance: {request}"
    else:
        pose_rule = "Create Xiaoxia in this requested pose: " + (request or "a natural full-body standing pose")
    return "\n\n".join([_xiaoxia_identity_block(), pose_rule, _standard_pose_asset_block()])


def _build_repair_prompt(user_text: str, has_pose_reference: bool) -> str:
    request = str(user_text or "").strip()
    text = (
        "Figure 1 is the current Xiaoxia candidate that needs pose correction. Figures 2-9 are Xiaoxia identity references. "
        "Keep Xiaoxia's face, hair, body identity and plain white pose-library outfit from those references. "
    )
    if has_pose_reference:
        text += (
            "Figure 10 is POSE REFERENCE ONLY. Correct Figure 1 so the skeleton and camera relationship match Figure 10 much more closely: "
            "pelvis orientation, torso lean and twist, shoulder rotation, head look-back direction, both arms and hand support points, "
            "knee placement, lower-leg folding, feet, weight distribution, camera side, camera height and crop. "
            "Do not copy Figure 10's person, face, hair, clothing or body identity. "
        )
    if request:
        text += f"User pose guidance: {request}. "
    text += "Make only the changes needed for pose fidelity; preserve Xiaoxia identity and the simple pose-library presentation."
    return text


async def _upload_file(fal_client: Any, path: str) -> str:
    url = await asyncio.to_thread(fal_client.upload_file, path)
    url = str(url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise RuntimeError("POSE_FAL_UPLOAD_NO_URL")
    return url


async def _attachment_to_persistent(attachment: discord.Attachment) -> str:
    suffix = os.path.splitext(str(getattr(attachment, "filename", "") or ""))[1].lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"
    path = _candidate_dir() / f"pose_ref_{uuid.uuid4().hex}{suffix}"
    await attachment.save(str(path))
    return str(path)


async def _download(url: str, target: Path) -> None:
    timeout = aiohttp.ClientTimeout(total=120)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"POSE_OUTPUT_DOWNLOAD_HTTP_{resp.status}")
            data = await resp.read()
    if not data:
        raise RuntimeError("POSE_OUTPUT_DOWNLOAD_EMPTY")
    target.write_bytes(data)


async def _run_model(app: Any, *, model_id: str, prompt: str, paths: List[str]) -> str:
    fal_client = app._get_fal_client()
    urls = []
    for path in paths:
        urls.append(await _upload_file(fal_client, path))
    args = {
        "prompt": prompt,
        "image_urls": urls,
        "image_size": os.environ.get("XIAOXIA_POSE_IMAGE_SIZE") or "portrait_16_9",
        "num_images": 1,
        "max_images": 1,
        "enable_safety_checker": _env_bool("XIAOXIA_POSE_ENABLE_SAFETY_CHECKER", True),
    }
    result = await asyncio.to_thread(lambda: fal_client.subscribe(model_id, arguments=args, with_logs=True))
    images = result.get("images") if isinstance(result, dict) else None
    image_url = images[0].get("url") if isinstance(images, list) and images and isinstance(images[0], dict) else None
    if not image_url:
        raise RuntimeError(f"POSE_MODEL_NO_IMAGE: {str(result)[:1000]}")
    return str(image_url)


async def generate_pose_candidate(app: Any, *, user_text: str = "", pose_attachment: Optional[discord.Attachment] = None,
                                  source_ref_path: str = "", repair_from: str = "") -> Dict[str, Any]:
    identity_paths = _identity_paths()
    if pose_attachment is not None:
        source_ref_path = await _attachment_to_persistent(pose_attachment)
    has_pose_reference = bool(source_ref_path and os.path.exists(source_ref_path))

    if repair_from:
        # 1 current candidate + 8 identity refs + optional pose ref = max 10 inputs.
        paths = [repair_from] + identity_paths[:8]
        if has_pose_reference:
            paths.append(source_ref_path)
        model_id = REPAIR_MODEL_ID
        prompt = _build_repair_prompt(user_text, has_pose_reference)
    else:
        paths = list(identity_paths)
        if has_pose_reference:
            paths.append(source_ref_path)
        model_id = MODEL_ID
        prompt = _build_prompt(user_text, has_pose_reference)

    print(f"💃 [POSE_CANDIDATE_START] model={model_id} refs={len(paths)} repair={bool(repair_from)}")
    image_url = await _run_model(app, model_id=model_id, prompt=prompt, paths=paths)
    candidate_path = _candidate_dir() / f"candidate_{int(time.time())}_{uuid.uuid4().hex[:8]}.png"
    await _download(image_url, candidate_path)
    return {
        "candidate_path": str(candidate_path),
        "source_ref_path": source_ref_path,
        "source": "image" if has_pose_reference else "text",
        "instruction": str(user_text or "").strip(),
        "model": model_id,
        "provider_url": image_url,
    }


def save_candidate(candidate: Dict[str, Any]) -> Dict[str, Any]:
    rows = _load_index()
    pose_id = _next_pose_id(rows)
    final_path = _files_dir() / f"{pose_id}.png"
    shutil.copy2(candidate["candidate_path"], final_path)
    row = {
        "id": pose_id,
        "name": str(candidate.get("instruction") or "").strip()[:120] or ("圖片姿勢" if candidate.get("source") == "image" else "姿勢"),
        "source": candidate.get("source") or "text",
        "instruction": str(candidate.get("instruction") or "").strip(),
        "file_path": str(final_path),
        "model": candidate.get("model") or MODEL_ID,
        "created_at": datetime.now().astimezone().isoformat(),
    }
    rows.insert(0, row)
    _save_index(rows)
    print(f"✅ [POSE_LIBRARY_SAVED] id={pose_id}")
    return row


def _safe_unlink(path: str) -> None:
    try:
        if path and os.path.exists(path):
            os.remove(path)
    except Exception:
        pass


class PoseReviewView(discord.ui.View):
    def __init__(self, app: Any, candidate: Dict[str, Any], owner_id: int):
        super().__init__(timeout=900)
        self.app = app
        self.candidate = candidate
        self.owner_id = owner_id
        self.done = False

    async def _owner_only(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner_id:
            await interaction.response.send_message("這張姿勢候選圖只能由原提出者操作。", ephemeral=True)
            return False
        return True

    def _disable(self):
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="收錄", emoji="✅", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._owner_only(interaction): return
        if self.done: return
        self.done = True
        row = save_candidate(self.candidate)
        self._disable()
        await interaction.response.edit_message(content=f"✅ **{row['id']} 已收入小俠姿勢庫**｜{row['model']}", view=self)

    @discord.ui.button(label="重抽", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def redraw(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._owner_only(interaction): return
        await interaction.response.defer()
        try:
            new = await generate_pose_candidate(self.app, user_text=self.candidate.get("instruction", ""), source_ref_path=self.candidate.get("source_ref_path", ""))
            view = PoseReviewView(self.app, new, self.owner_id)
            await interaction.followup.send("🔄 **新候選圖（Seedream v4.5）**｜滿意再收錄。", file=discord.File(new["candidate_path"]), view=view)
        except Exception as exc:
            await interaction.followup.send(f"⚠️ 重抽失敗：`{type(exc).__name__}: {str(exc)[:800]}`")

    @discord.ui.button(label="V5 修姿勢", emoji="✏️", style=discord.ButtonStyle.primary)
    async def repair(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._owner_only(interaction): return
        await interaction.response.defer()
        try:
            new = await generate_pose_candidate(
                self.app,
                user_text=self.candidate.get("instruction", ""),
                source_ref_path=self.candidate.get("source_ref_path", ""),
                repair_from=self.candidate["candidate_path"],
            )
            view = PoseReviewView(self.app, new, self.owner_id)
            await interaction.followup.send(f"✏️ **Seedream V5 修姿勢候選圖**｜模型：`{REPAIR_MODEL_ID}`｜滿意再收錄。", file=discord.File(new["candidate_path"]), view=view)
        except Exception as exc:
            await interaction.followup.send(f"⚠️ V5 修姿勢失敗：`{type(exc).__name__}: {str(exc)[:800]}`")

    @discord.ui.button(label="放棄", emoji="❌", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._owner_only(interaction): return
        if self.done: return
        self.done = True
        _safe_unlink(self.candidate.get("candidate_path", ""))
        self._disable()
        await interaction.response.edit_message(content="❌ 已放棄這張候選圖，未收入姿勢庫。", view=self)


def load_pose_library() -> List[Dict[str, Any]]:
    return _load_index()


def pose_reference_for_generation(pose_id: str) -> Optional[str]:
    wanted = str(pose_id or "").strip().upper()
    for row in _load_index():
        if str(row.get("id") or "").strip().upper() == wanted:
            path = str(row.get("file_path") or "").strip()
            return path if path and os.path.exists(path) else None
    return None


def install_pose_commands(app: Any) -> Dict[str, Any]:
    bot = getattr(app, "girlfriend_bot", None)
    if bot is None:
        raise RuntimeError("girlfriend_bot not found")
    for name in ("姿勢", "姿勢庫"):
        try: bot.remove_command(name)
        except Exception: pass

    @bot.command(name="姿勢")
    async def pose_command(ctx, *, request: str = ""):
        text = str(request or "").strip()
        for prefix in ("建立", "換人"):
            if text.startswith(prefix):
                text = text[len(prefix):].lstrip(" ：:，,")
                break
        attachments = list(getattr(getattr(ctx, "message", None), "attachments", []) or [])
        pose_attachment = next((a for a in attachments if str(getattr(a, "content_type", "") or "").startswith("image/") or str(getattr(a, "filename", "") or "").lower().endswith((".jpg", ".jpeg", ".png", ".webp"))), None)
        if not text and pose_attachment is None:
            await ctx.reply("💃 用法：`/姿勢 <文字描述>`，或附姿勢圖後輸入 `/姿勢 換人`。生成後先審核，不會自動入庫。", mention_author=False)
            return
        status = await ctx.reply("💃 正在建立姿勢**候選圖**…不會自動收入姿勢庫。", mention_author=False)
        try:
            candidate = await generate_pose_candidate(app, user_text=text, pose_attachment=pose_attachment)
            view = PoseReviewView(app, candidate, ctx.author.id)
            await ctx.reply("🧪 **姿勢候選圖**｜請選：✅收錄／🔄重抽／✏️V5修姿勢／❌放棄", file=discord.File(candidate["candidate_path"]), view=view, mention_author=False)
            try: await status.delete()
            except Exception: pass
        except Exception as exc:
            try: await status.edit(content=f"⚠️ 姿勢候選圖建立失敗：`{type(exc).__name__}: {str(exc)[:1200]}`")
            except Exception: pass

    @bot.command(name="姿勢庫")
    async def pose_library_command(ctx, *, request: str = ""):
        text = str(request or "").strip()
        m = re.match(r"^(?:刪除|delete)\s+(P\d+)$", text, re.I)
        if m:
            wanted = m.group(1).upper()
            rows = _load_index()
            hit = next((r for r in rows if str(r.get("id") or "").upper() == wanted), None)
            if not hit:
                await ctx.reply(f"找不到 `{wanted}`。", mention_author=False); return
            _safe_unlink(str(hit.get("file_path") or ""))
            rows = [r for r in rows if str(r.get("id") or "").upper() != wanted]
            _save_index(rows)
            await ctx.reply(f"🗑️ `{wanted}` 已從姿勢庫刪除。", mention_author=False); return
        rows = _load_index()
        if not rows:
            await ctx.reply("💃 姿勢庫目前是空的。", mention_author=False); return
        lines = [f"💃 **小俠姿勢庫**｜共 {len(rows)} 張"]
        for row in rows[:20]:
            source = "圖" if row.get("source") == "image" else "文"
            lines.append(f"`{row.get('id')}` [{source}] {str(row.get('name') or '姿勢')[:70]}")
        await ctx.reply("\n".join(lines), mention_author=False)

    app.pose_reference_for_generation = pose_reference_for_generation
    app.load_pose_library = load_pose_library
    return {"patched": True, "commands": ["/姿勢", "/姿勢庫"], "model": MODEL_ID, "repair_model": REPAIR_MODEL_ID, "review_before_save": True}
