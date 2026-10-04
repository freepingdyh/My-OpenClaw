# -*- coding: utf-8 -*-
"""Qwen Image 2.1 mark-based local repair command for Xiaoxia.

MVP contract:
- mark_image: the single marked composite image. This is the same image the user wants
  to repair, with circles / painted annotations drawn directly on it.
- delta: what to change inside the marked region(s).
- no separate clean source image and no Xiaoxia identity/body reference images are
  sent to Qwen in this path.

This is deliberately separate from the existing Seedream "修正這張" path so the
old repair flow remains an immediate rollback option while Qwen local-edit quality
is evaluated.
"""
from __future__ import annotations

import os
import secrets
import uuid
from pathlib import Path
from typing import Any, Dict

import discord
from discord import app_commands

from xiaoxia.media.runpod_serverless import RunPodServerlessError, run_qwen21

VERSION = "1.0.2-qwen-fix-v3-shared-core"

_ROOT = Path("/data/memory/qwen21")
_RUNS_DIR = _ROOT / "fix_runs"
_UPLOADS_DIR = _RUNS_DIR / "_uploads"
_MARK_IMAGE_NAME = "qwen_fix_mark.png"

SYSTEM_CORE_PROMPT = """QWEN FIX — MARK-BASED LOCAL EDIT

<image1> is the single marked composite image to edit.
The circles, painted annotations, arrows, or scribbles on <image1> indicate the local
region(s) that should change. They are editing guides only and must not appear in the
final image.

Modify only the marked region(s) according to the USER DELTA.
Preserve all unmarked content as closely as possible, including identity, face,
hairstyle, expression, pose, body orientation, camera angle, framing, crop, background,
scene layout, lighting, color, texture, clothing, props, and unrelated details.

After applying the requested local repair, remove all visible annotation marks and
return a clean final image. Do not restage the image, reinterpret the whole scene, or
make broad global changes. Do not add extra people, clones, duplicate subjects, or
extra body parts.
""".strip()


def _effective_prompt(delta: str) -> str:
    request = str(delta or "").strip()
    if not request:
        request = "Repair only the marked region(s) naturally while preserving all unmarked areas."
    return SYSTEM_CORE_PROMPT + "\n\nUSER DELTA:\n" + request


def _is_image_attachment(attachment: discord.Attachment) -> bool:
    content_type = str(getattr(attachment, "content_type", "") or "").lower()
    filename = str(getattr(attachment, "filename", "") or "").lower()
    return content_type.startswith("image/") or filename.endswith((".png", ".jpg", ".jpeg", ".webp"))


def _ext(attachment: discord.Attachment) -> str:
    name = str(getattr(attachment, "filename", "") or "").lower()
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        if name.endswith(ext):
            return ext
    return ".png"


def _ensure_dirs() -> None:
    _UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


async def run_mark_fix_bytes(
    mark_bytes: bytes,
    delta: str,
    *,
    steps: int = 40,
    seed: int | None = None,
) -> tuple[bytes, int]:
    """Single SSOT for Qwen marked-image Local Edit.

    Both /qwen_fix and the photo "修正這張" flow must call this exact function so
    model input, prompt, seed handling, steps, and disabled reference slots cannot drift.
    """
    if not mark_bytes:
        raise ValueError("mark image bytes are empty")

    actual_seed = int(seed) if seed is not None else secrets.randbelow(2**63 - 1)

    results = await run_qwen21(
        mark_bytes,
        prompt=prompt,
        seed=actual_seed,
        steps=int(steps),
        disabled_image_slots={2, 3, 4, 5, 6},
    )
    if not results:
        raise RunPodServerlessError("Qwen marked-image Local Edit returned no image")

    _, blob = results[0]
    return blob, actual_seed


async def _run_fix(
    interaction: discord.Interaction,
    *,
    mark_bytes: bytes,
    delta: str,
    count: int,
    steps: int,
) -> None:
    prompt = _effective_prompt(delta)
    status = await interaction.followup.send(
        f"🩹 Qwen Fix 正在進行 mark-based 局部修正，候選 {count} 張…",
        wait=True,
    )
    completed = 0
    try:
        for index in range(1, int(count) + 1):
            blob, seed = await run_mark_fix_bytes(
                mark_bytes,
                delta,
                steps=int(steps),
            )
            filename = f"qwen_fix_{uuid.uuid4().hex[:10]}_{index}.png"
            await interaction.followup.send(
                (
                    f"🩹 **Qwen Fix** | Candidate {index}/{count}\n"
                    f"Delta: {str(delta or '').strip() or '—'}\n"
                    f"Steps: {steps} | Seed: {seed}"
                ),
                file=discord.File(fp=__import__("io").BytesIO(blob), filename=filename),
            )
            completed += 1
            try:
                await status.edit(content=f"🩹 Qwen Fix：已完成 {completed}/{count} 張…")
            except Exception:
                pass
    finally:
        try:
            await status.delete()
        except Exception:
            pass

    print(
        f"✅ [QWEN_FIX_RUN] version={VERSION} refs=marked_image_only "
        f"count={completed}/{count} steps={steps}"
    )


def install_qwen_fix(app: Any) -> Dict[str, Any]:
    bot = app.girlfriend_bot
    tree = bot.tree

    async def qwen_fix_command(
        interaction: discord.Interaction,
        mark_image: discord.Attachment,
        delta: str,
        count: app_commands.Range[int, 1, 4] = 1,
        steps: app_commands.Range[int, 20, 50] = 40,
    ):
        if not _is_image_attachment(mark_image):
            await interaction.response.send_message("⚠️ mark_image 必須是圖片。", ephemeral=True)
            return
        if not os.environ.get("XIAOXIA_RUNPOD_SERVERLESS_ENDPOINT_ID") or not (
            os.environ.get("XIAOXIA_RUNPOD_SERVERLESS_API_KEY")
            or os.environ.get("RUNPOD_API_KEY")
        ):
            await interaction.response.send_message("⚠️ RunPod Qwen21 Serverless 尚未設定。", ephemeral=True)
            return

        await interaction.response.defer(thinking=True)
        _ensure_dirs()
        mark_bytes = await mark_image.read()
        if not mark_bytes:
            await interaction.followup.send("⚠️ mark 圖為空，無法修正。", ephemeral=True)
            return

        # Keep the exact marked composite for debugging/reproducibility.
        run_tag = f"{interaction.id}_{uuid.uuid4().hex[:6]}"
        (_UPLOADS_DIR / f"{run_tag}_mark{_ext(mark_image)}").write_bytes(mark_bytes)

        try:
            await _run_fix(
                interaction,
                mark_bytes=mark_bytes,
                delta=str(delta or "").strip(),
                count=int(count),
                steps=int(steps),
            )
        except Exception as exc:
            print(f"❌ [QWEN_FIX_ERROR] {type(exc).__name__}: {exc}")
            await interaction.followup.send(
                f"⚠️ Qwen Fix 失敗：`{type(exc).__name__}: {str(exc)[:1200]}`",
                ephemeral=True,
            )

    command = app_commands.Command(
        name="qwen_fix",
        description="Qwen 2.1 局部修正：上傳已圈選/塗記的圖片與 Delta",
        callback=qwen_fix_command,
    )
    command._params["mark_image"].description = "已標註圖：直接在要修的照片上圈選/塗記目標區域"
    command._params["delta"].description = "只描述標註區域要怎麼修改"
    command._params["count"].description = "候選張數（1~4）"
    command._params["steps"].description = "Qwen sampling steps（20~50，預設40）"
    tree.add_command(command, override=True)

    original_ready = getattr(bot, "on_ready", None)
    synced = False

    async def on_ready_with_qwen_fix_sync():
        nonlocal synced
        if original_ready is not None:
            await original_ready()
        if synced:
            return
        try:
            synced_cmds = await tree.sync()
            synced = True
            print(f"✅ [QWEN_FIX_SLASH_SYNC] version={VERSION} synced={len(synced_cmds)}")
        except Exception as exc:
            print(f"❌ [QWEN_FIX_SLASH_SYNC_FAILED] {type(exc).__name__}: {exc}")

    bot.on_ready = on_ready_with_qwen_fix_sync

    return {
        "version": VERSION,
        "command": "qwen_fix",
        "input_contract": "marked_composite_plus_delta",
        "qwen_reference_policy": "marked_image_only",
        "seedream_repair_unchanged": True,
    }
