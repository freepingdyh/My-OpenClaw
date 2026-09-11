# -*- coding: utf-8 -*-
"""Xiaoxia Pose Library.

Image pose conversion uses Seedream v5 Pro Edit with exactly two references:
1) the user's source/pose image as the base canvas and geometry authority;
2) one canonical Xiaoxia identity image as the identity authority.

Text-only pose generation keeps the older Seedream v4.5 multi-identity path because
there is no source canvas to edit.

All results are candidates first. Nothing enters the persistent pose library until
its owner presses the Discord '收錄' button.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import shutil
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
import discord

TEXT_MODEL_ID = "fal-ai/bytedance/seedream/v4.5/edit"
IMAGE_MODEL_ID = os.environ.get("XIAOXIA_POSE_V5_MODEL") or "bytedance/seedream/v5/pro/edit"
POSE_VERSION = "1.12.06ao"


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
    """Nine canonical refs used only by text-only v4.5 generation."""
    raw = str(os.environ.get("XIAOXIA_POSE_IDENTITY_REFS") or "").strip()
    if raw:
        candidates = [x.strip() for x in re.split(r"[;,\n]+", raw) if x.strip()]
    else:
        candidates = [f"dataset/Xiaoxia_{i:03d}.png" for i in range(1, 10)]
    existing = [p for p in candidates if os.path.exists(p)]
    if len(existing) < 9:
        raise RuntimeError(f"POSE_IDENTITY_REFS_NEED_9: found={len(existing)}")
    return existing[:9]


def _v5_identity_path() -> str:
    """One Xiaoxia identity reference for Seedream v5 image editing."""
    configured = str(os.environ.get("XIAOXIA_POSE_V5_IDENTITY_REF") or "").strip()
    candidates: List[str] = []
    if configured:
        candidates.append(configured)
    # The first canonical identity is the deterministic default. It can be replaced
    # without code changes through XIAOXIA_POSE_V5_IDENTITY_REF after A/B testing.
    candidates.extend(["dataset/Xiaoxia_001.png", "dataset/Xiaoxia_002.png", "dataset/Xiaoxia_003.png"])
    for path in candidates:
        if path and os.path.exists(path):
            return path
    raise RuntimeError("POSE_V5_IDENTITY_REF_NOT_FOUND: set XIAOXIA_POSE_V5_IDENTITY_REF")


def _text_identity_block() -> str:
    return (
        "Figures 1-9 are canonical identity references for one and the same adult woman, Xiaoxia. "
        "Preserve her facial identity and proportions, long brown slightly wavy hair with airy bangs, "
        "and her consistent adult body identity. Do not invent another person."
    )


def _standard_pose_asset_block() -> str:
    return (
        "The output is a reusable pose-library asset. Use a plain fitted white sleeveless top and plain "
        "white shorts, no logos, jewelry or hat. Use a clean neutral light-gray studio background unless "
        "the pose physically requires a minimal support surface. Keep the pose clearly readable."
    )


def _build_text_prompt(user_text: str) -> str:
    request = str(user_text or "").strip() or "a natural full-body standing pose"
    return "\n\n".join([
        _text_identity_block(),
        f"Create Xiaoxia in this requested pose: {request}",
        _standard_pose_asset_block(),
    ])


def _build_v5_image_prompt(user_text: str) -> str:
    """V5 two-image edit contract.

    Figure 1 is deliberately first: it is the image to edit and the sole pose/camera
    authority. Figure 2 provides Xiaoxia identity only.
    """
    request = str(user_text or "").strip()
    text = (
        "Edit Figure 1. Figure 1 is the base image and absolute authority for pose, body placement, "
        "limb placement, hand and foot positions, torso direction, head direction, camera angle, camera "
        "height, framing, crop and perspective. Preserve those geometric relationships as closely as possible. "
        "Replace the woman in Figure 1 with the same adult woman shown in Figure 2, Xiaoxia. Figure 2 is "
        "IDENTITY REFERENCE ONLY: use it for Xiaoxia's face identity, facial proportions and recognizable "
        "personal appearance. Do not copy Figure 2's pose, framing, background or clothing. "
        "Change the outfit to a plain fitted white sleeveless top and plain white shorts. Replace the background "
        "with a clean neutral light-gray studio background while retaining any minimal support surface that is "
        "physically necessary for the pose. Do not beautify into a different person and do not redesign the pose."
    )
    if request:
        text += f" Additional user instruction: {request}."
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
    urls = [await _upload_file(fal_client, path) for path in paths]
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


async def generate_pose_candidate(
    app: Any,
    *,
    user_text: str = "",
    pose_attachment: Optional[discord.Attachment] = None,
    source_ref_path: str = "",
) -> Dict[str, Any]:
    if pose_attachment is not None:
        source_ref_path = await _attachment_to_persistent(pose_attachment)
    has_pose_reference = bool(source_ref_path and os.path.exists(source_ref_path))

    if has_pose_reference:
        # Seedream v5 image-edit path: exactly 2 refs.
        # Figure 1 = source/base canvas (pose authority)
        # Figure 2 = one Xiaoxia identity image (identity authority)
        identity_path = _v5_identity_path()
        paths = [source_ref_path, identity_path]
        model_id = IMAGE_MODEL_ID
        prompt = _build_v5_image_prompt(user_text)
        mode = "v5_two_ref_edit"
    else:
        # Text-only generation has no base image, so retain the proven v4.5 identity route.
        paths = _identity_paths()
        model_id = TEXT_MODEL_ID
        prompt = _build_text_prompt(user_text)
        mode = "v45_text_generation"

    print(f"💃 [POSE_CANDIDATE_START] model={model_id} refs={len(paths)} mode={mode}")
    image_url = await _run_model(app, model_id=model_id, prompt=prompt, paths=paths)
    candidate_path = _candidate_dir() / f"candidate_{int(time.time())}_{uuid.uuid4().hex[:8]}.png"
    await _download(image_url, candidate_path)
    return {
        "candidate_path": str(candidate_path),
        "source_ref_path": source_ref_path,
        "source": "image" if has_pose_reference else "text",
        "instruction": str(user_text or "").strip(),
        "model": model_id,
        "mode": mode,
        "input_ref_count": len(paths),
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
        "model": candidate.get("model") or IMAGE_MODEL_ID,
        "mode": candidate.get("mode") or "",
        "input_ref_count": int(candidate.get("input_ref_count") or 0),
        "created_at": datetime.now().astimezone().isoformat(),
    }
    rows.insert(0, row)
    _save_index(rows)
    print(f"✅ [POSE_LIBRARY_SAVED] id={pose_id} mode={row['mode']}")
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

    def _disable(self) -> None:
        for item in self.children:
            item.disabled = True

    @discord.ui.button(label="收錄", emoji="✅", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._owner_only(interaction):
            return
        if self.done:
            return
        self.done = True
        row = save_candidate(self.candidate)
        self._disable()
        await interaction.response.edit_message(
            content=f"✅ **{row['id']} 已收入小俠姿勢庫**｜{row['model']}｜refs={row['input_ref_count']}",
            view=self,
        )

    @discord.ui.button(label="重抽", emoji="🔄", style=discord.ButtonStyle.secondary)
    async def redraw(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._owner_only(interaction):
            return
        await interaction.response.defer()
        try:
            new = await generate_pose_candidate(
                self.app,
                user_text=self.candidate.get("instruction", ""),
                source_ref_path=self.candidate.get("source_ref_path", ""),
            )
            view = PoseReviewView(self.app, new, self.owner_id)
            label = "Seedream V5｜2 refs" if new.get("source") == "image" else "Seedream v4.5｜文字姿勢"
            await interaction.followup.send(
                f"🔄 **新姿勢候選圖**｜{label}｜滿意再收錄。",
                file=discord.File(new["candidate_path"]),
                view=view,
            )
        except Exception as exc:
            await interaction.followup.send(f"⚠️ 重抽失敗：`{type(exc).__name__}: {str(exc)[:800]}`")

    @discord.ui.button(label="放棄", emoji="❌", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._owner_only(interaction):
            return
        if self.done:
            return
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
        try:
            bot.remove_command(name)
        except Exception:
            pass

    @bot.command(name="姿勢")
    async def pose_command(ctx, *, request: str = ""):
        text = str(request or "").strip()
        for prefix in ("建立", "換人"):
            if text.startswith(prefix):
                text = text[len(prefix):].lstrip(" ：:，,")
                break

        attachments = list(getattr(getattr(ctx, "message", None), "attachments", []) or [])
        pose_attachment = next(
            (
                a for a in attachments
                if str(getattr(a, "content_type", "") or "").startswith("image/")
                or str(getattr(a, "filename", "") or "").lower().endswith((".jpg", ".jpeg", ".png", ".webp"))
            ),
            None,
        )

        if not text and pose_attachment is None:
            await ctx.reply(
                "💃 用法：附姿勢圖後輸入 `/姿勢 換人`（Seedream V5：原圖 + 1 張小俠 Identity），"
                "或用 `/姿勢 <文字描述>` 建立文字姿勢。生成後先審核，不會自動入庫。",
                mention_author=False,
            )
            return

        if pose_attachment is not None:
            status_text = "💃 正在用 **Seedream V5** 換成小俠姿勢候選圖…｜2 refs：原姿勢圖 + 1 張小俠 Identity｜不會自動入庫。"
        else:
            status_text = "💃 正在建立文字姿勢候選圖…｜Seedream v4.5｜不會自動入庫。"
        status = await ctx.reply(status_text, mention_author=False)

        try:
            candidate = await generate_pose_candidate(app, user_text=text, pose_attachment=pose_attachment)
            view = PoseReviewView(app, candidate, ctx.author.id)
            if candidate["source"] == "image":
                caption = "🧪 **V5 姿勢換人候選圖**｜原圖掌管姿勢／1 張小俠圖掌管身份｜請選：✅收錄／🔄重抽／❌放棄"
            else:
                caption = "🧪 **文字姿勢候選圖**｜請選：✅收錄／🔄重抽／❌放棄"
            await ctx.reply(
                caption,
                file=discord.File(candidate["candidate_path"]),
                view=view,
                mention_author=False,
            )
            try:
                await status.delete()
            except Exception:
                pass
        except Exception as exc:
            try:
                await status.edit(content=f"⚠️ 姿勢候選圖建立失敗：`{type(exc).__name__}: {str(exc)[:1200]}`")
            except Exception:
                pass

    @bot.command(name="姿勢庫")
    async def pose_library_command(ctx, *, request: str = ""):
        text = str(request or "").strip()
        m = re.match(r"^(?:刪除|delete)\s+(P\d+)$", text, re.I)
        if m:
            wanted = m.group(1).upper()
            rows = _load_index()
            hit = next((r for r in rows if str(r.get("id") or "").upper() == wanted), None)
            if not hit:
                await ctx.reply(f"找不到 `{wanted}`。", mention_author=False)
                return
            _safe_unlink(str(hit.get("file_path") or ""))
            rows = [r for r in rows if str(r.get("id") or "").upper() != wanted]
            _save_index(rows)
            await ctx.reply(f"🗑️ `{wanted}` 已從姿勢庫刪除。", mention_author=False)
            return

        rows = _load_index()
        if not rows:
            await ctx.reply("💃 姿勢庫目前是空的。", mention_author=False)
            return
        lines = [f"💃 **小俠姿勢庫**｜共 {len(rows)} 張"]
        for row in rows[:20]:
            source = "圖" if row.get("source") == "image" else "文"
            lines.append(f"`{row.get('id')}` [{source}] {str(row.get('name') or '姿勢')[:70]}")
        await ctx.reply("\n".join(lines), mention_author=False)

    app.pose_reference_for_generation = pose_reference_for_generation
    app.load_pose_library = load_pose_library
    return {
        "patched": True,
        "commands": ["/姿勢", "/姿勢庫"],
        "image_model": IMAGE_MODEL_ID,
        "image_refs": 2,
        "text_model": TEXT_MODEL_ID,
        "review_before_save": True,
    }
