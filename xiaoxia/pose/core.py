# -*- coding: utf-8 -*-
"""Xiaoxia pose-library producer for Seedream v4.5.

Two inputs, one pipeline:
- text only -> generate a new Xiaoxia pose from the requested body pose;
- attached pose image -> use it only for pose/camera relationship, while Xiaoxia identity
  is defined by nine fixed identity references.

Every successful result is stored as a reusable pose asset under persistent storage.
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import aiohttp
import discord

MODEL_ID = "fal-ai/bytedance/seedream/v4.5/edit"
POSE_VERSION = "1.12.06am"


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
    """Return exactly nine Xiaoxia identity references.

    XIAOXIA_POSE_IDENTITY_REFS may override defaults with comma/semicolon-separated paths.
    The default intentionally uses nine local Xiaoxia reference files so an optional pose
    reference can occupy image slot 10, matching Seedream v4.5's current 10-input limit.
    """
    raw = str(os.environ.get("XIAOXIA_POSE_IDENTITY_REFS") or "").strip()
    if raw:
        candidates = [x.strip() for x in re.split(r"[;,\n]+", raw) if x.strip()]
    else:
        candidates = [f"dataset/Xiaoxia_{i:03d}.png" for i in range(1, 10)]
    existing = [p for p in candidates if os.path.exists(p)]
    if len(existing) < 9:
        raise RuntimeError(
            f"POSE_IDENTITY_REFS_NEED_9: found={len(existing)}; "
            "set XIAOXIA_POSE_IDENTITY_REFS if the canonical nine references live elsewhere"
        )
    return existing[:9]


def _xiaoxia_identity_block() -> str:
    return (
        "Figures 1-9 are the canonical identity references for one and the same adult woman, Xiaoxia. "
        "They have highest priority for identity. Preserve her face identity and facial proportions, "
        "fair skin, tall slender build, long brown slightly wavy hair with airy bangs, youthful sweet "
        "East Asian appearance, elegant long-limbed proportions, defined waist, and her naturally full "
        "bust characteristic from the identity references, allowed to be only subtly fuller while still "
        "natural and consistent. She is 24 years old. Do not average her identity with any other person. "
        "If pose accuracy conflicts with identity, keep Xiaoxia's identity."
    )


def _standard_pose_asset_block() -> str:
    return (
        "This is a reusable Xiaoxia Pose Library asset, not a final scene photo. "
        "Use a simple fitted white sleeveless top and simple white shorts, no logos, no jewelry, no hat, "
        "and bare feet when natural. Use a clean neutral light-gray studio background unless the requested "
        "pose physically needs a bed, sofa, chair, wall, floor support, or similar minimal support object. "
        "Keep the body pose clearly readable; show the full body whenever the pose depends on legs, knees, "
        "feet, kneeling, sitting, crouching, or full-body balance. Maintain anatomically natural hands, feet, "
        "joint directions, weight distribution and torso twist."
    )


def _build_prompt(user_text: str, has_pose_reference: bool) -> str:
    identity = _xiaoxia_identity_block()
    asset = _standard_pose_asset_block()
    request = str(user_text or "").strip()
    if has_pose_reference:
        pose_rule = (
            "Figure 10 is POSE REFERENCE ONLY. Copy its body pose, limb placement, torso direction, head "
            "direction, weight distribution, camera relationship and broad framing. Do not copy Figure 10's "
            "face, identity, age, hair, skin tone, body shape, clothing, accessories or personal features. "
            "Recreate that pose as Xiaoxia from Figures 1-9."
        )
        if request:
            pose_rule += f" Additional user pose guidance: {request}"
    else:
        pose_rule = (
            "Create Xiaoxia in this requested pose, keeping the pose visually clear and natural: "
            + (request or "a graceful natural full-body standing pose with a subtle torso turn toward camera")
        )
    return "\n\n".join([identity, pose_rule, asset])


async def _upload_file(fal_client: Any, path: str) -> str:
    url = await asyncio.to_thread(fal_client.upload_file, path)
    url = str(url or "").strip()
    if not url.startswith(("http://", "https://")):
        raise RuntimeError("POSE_FAL_UPLOAD_NO_URL")
    return url


async def _attachment_to_temp(attachment: discord.Attachment) -> str:
    suffix = os.path.splitext(str(getattr(attachment, "filename", "") or ""))[1].lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp"}:
        suffix = ".jpg"
    fd, path = tempfile.mkstemp(prefix="xiaoxia_pose_ref_", suffix=suffix)
    os.close(fd)
    await attachment.save(path)
    return path


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


async def generate_pose_asset(app: Any, *, user_text: str = "", pose_attachment: Optional[discord.Attachment] = None) -> Dict[str, Any]:
    fal_client = app._get_fal_client()
    identity_paths = _identity_paths()
    uploaded_identity = []
    for idx, path in enumerate(identity_paths, start=1):
        uploaded_identity.append(await _upload_file(fal_client, path))
        print(f"💃 [POSE_IDENTITY_UPLOAD] figure={idx} path={path}")

    pose_temp = None
    try:
        image_urls = list(uploaded_identity)
        if pose_attachment is not None:
            pose_temp = await _attachment_to_temp(pose_attachment)
            pose_url = await _upload_file(fal_client, pose_temp)
            image_urls.append(pose_url)
            print("💃 [POSE_REFERENCE_UPLOAD] figure=10 source=discord_attachment")

        prompt = _build_prompt(user_text, pose_attachment is not None)
        args = {
            "prompt": prompt,
            "image_urls": image_urls,
            "image_size": os.environ.get("XIAOXIA_POSE_IMAGE_SIZE") or "portrait_16_9",
            "num_images": 1,
            "max_images": 1,
            "enable_safety_checker": _env_bool("XIAOXIA_POSE_ENABLE_SAFETY_CHECKER", True),
        }

        def _subscribe():
            return fal_client.subscribe(MODEL_ID, arguments=args, with_logs=True)

        print(f"💃 [POSE_SEEDREAM_START] refs={len(image_urls)} source={'image' if pose_attachment else 'text'}")
        result = await asyncio.to_thread(_subscribe)
        images = result.get("images") if isinstance(result, dict) else None
        image_url = images[0].get("url") if isinstance(images, list) and images and isinstance(images[0], dict) else None
        if not image_url:
            raise RuntimeError(f"POSE_SEEDREAM_NO_IMAGE: {str(result)[:1200]}")

        rows = _load_index()
        pose_id = _next_pose_id(rows)
        filename = f"{pose_id}.png"
        local_path = _files_dir() / filename
        await _download(str(image_url), local_path)
        row = {
            "id": pose_id,
            "name": str(user_text or "").strip()[:120] or ("圖片姿勢" if pose_attachment else "姿勢"),
            "source": "image" if pose_attachment else "text",
            "instruction": str(user_text or "").strip(),
            "file_path": str(local_path),
            "model": MODEL_ID,
            "identity_ref_count": 9,
            "total_input_count": len(image_urls),
            "created_at": datetime.now().astimezone().isoformat(),
        }
        rows.insert(0, row)
        _save_index(rows)
        print(f"✅ [POSE_LIBRARY_SAVED] id={pose_id} source={row['source']} refs={len(image_urls)}")
        return {**row, "provider_url": image_url}
    finally:
        if pose_temp and os.path.exists(pose_temp):
            try:
                os.remove(pose_temp)
            except Exception:
                pass


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
            (a for a in attachments if str(getattr(a, "content_type", "") or "").startswith("image/")
             or str(getattr(a, "filename", "") or "").lower().endswith((".jpg", ".jpeg", ".png", ".webp"))),
            None,
        )
        if not text and pose_attachment is None:
            await ctx.reply(
                "💃 用法：`/姿勢 <文字描述>`，或附一張姿勢圖後輸入 `/姿勢`。也可以圖＋文字一起給。",
                mention_author=False,
            )
            return
        status = await ctx.reply(
            f"💃 正在用 Seedream v4.5 建立小俠姿勢底圖…｜9 張 Identity + {'1 張 Pose' if pose_attachment else '文字姿勢'}",
            mention_author=False,
        )
        try:
            result = await generate_pose_asset(app, user_text=text, pose_attachment=pose_attachment)
            path = result["file_path"]
            caption = (
                f"✅ **{result['id']} 已收入小俠姿勢庫**\n"
                f"來源：{'姿勢圖換人' if result['source'] == 'image' else '文字生成'}｜Seedream v4.5\n"
                f"Identity：9 張小俠底圖"
            )
            if text:
                caption += f"\n姿勢：{text[:400]}"
            await ctx.reply(caption, file=discord.File(path, filename=os.path.basename(path)), mention_author=False)
            try:
                await status.delete()
            except Exception:
                pass
        except Exception as exc:
            print(f"❌ [POSE_LIBRARY_ERROR] {type(exc).__name__}: {exc}")
            try:
                await status.edit(content=f"⚠️ 姿勢底圖建立失敗：`{type(exc).__name__}: {str(exc)[:1200]}`")
            except Exception:
                await ctx.reply(f"⚠️ 姿勢底圖建立失敗：`{type(exc).__name__}: {str(exc)[:1200]}`", mention_author=False)

    @bot.command(name="姿勢庫")
    async def pose_library_command(ctx):
        rows = _load_index()
        if not rows:
            await ctx.reply("💃 姿勢庫目前是空的。先用 `/姿勢 <描述>` 或附姿勢圖後 `/姿勢` 建立第一張。", mention_author=False)
            return
        lines = [f"💃 **小俠姿勢庫**｜共 {len(rows)} 張"]
        for row in rows[:20]:
            title = str(row.get("name") or "姿勢").strip()
            source = "圖" if row.get("source") == "image" else "文"
            lines.append(f"`{row.get('id')}` [{source}] {title[:70]}")
        if len(rows) > 20:
            lines.append(f"…另有 {len(rows)-20} 張")
        await ctx.reply("\n".join(lines), mention_author=False)

    app.pose_reference_for_generation = pose_reference_for_generation
    app.load_pose_library = load_pose_library
    return {
        "patched": True,
        "commands": ["/姿勢", "/姿勢庫"],
        "model": MODEL_ID,
        "identity_refs": 9,
        "image_mode_total_refs": 10,
        "text_mode": True,
        "image_mode": True,
        "persistent_library": str(_root_dir()),
    }
