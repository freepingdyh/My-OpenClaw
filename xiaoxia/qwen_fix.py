# -*- coding: utf-8 -*-
"""Qwen Image 2.1 mark-based local repair command for Xiaoxia.

MVP contract:
- image_1: untouched original/source image and edit canvas.
- mark_image: a copy of the same image with circles / painted annotations marking
  only the region(s) to change.
- delta: what to change inside the marked region(s).
- no Xiaoxia identity/body reference images are active in this path.

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

VERSION = "1.0.0-qwen-fix-v1"

_ROOT = Path("/data/memory/qwen21")
_RUNS_DIR = _ROOT / "fix_runs"
_UPLOADS_DIR = _RUNS_DIR / "_uploads"
_MARK_IMAGE_NAME = "qwen_fix_mark.png"

SYSTEM_CORE_PROMPT = """QWEN FIX — MARK-BASED LOCAL EDIT

<image1> is the ORIGINAL image and the only output canvas to edit.
<image2> is the SAME image with circles, painted annotations, or markings that identify
the target region(s) for this repair.

Use <image2> only to locate the marked repair region(s).
Do not copy the annotation marks themselves into the output.

Modify only the marked region(s). Preserve everything outside the marked region(s)
from <image1> as closely as possible, including identity, face, hairstyle, expression,
pose, body orientation, hand placement, camera angle, framing, crop, background,
scene layout, lighting, color, texture, clothing, props, and unrelated details.

Do not restage the image, do not reinterpret the whole scene, and do not make broad
global changes. Do not add extra people, clones, duplicate subjects, or extra body parts.

The USER DELTA defines what should be changed inside the marked region(s).
Apply it precisely and keep unmarked areas stable.
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


async def _run_fix(
    interaction: discord.Interaction,
    *,
    source_bytes: bytes,
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
            seed = secrets.randbelow(2**63 - 1)
            results = await run_qwen21(
                source_bytes,
                prompt=prompt,
                seed=seed,
                steps=int(steps),
                workflow_image_replacements={
                    "image_2_face_front.png": _MARK_IMAGE_NAME,
                },
                extra_images={
                    _MARK_IMAGE_NAME: mark_bytes,
                },
                disabled_image_slots={3, 4, 5, 6},
            )
            if not results:
                raise RunPodServerlessError(f"candidate {index} returned no image")
            _, blob = results[0]
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
        f"✅ [QWEN_FIX_RUN] version={VERSION} refs=image1+mark_image "
        f"count={completed}/{count} steps={steps}"
    )


def install_qwen_fix(app: Any) -> Dict[str, Any]:
    bot = app.girlfriend_bot
    tree = bot.tree

    async def qwen_fix_command(
        interaction: discord.Interaction,
        image_1: discord.Attachment,
        mark_image: discord.Attachment,
        delta: str,
        count: app_commands.Range[int, 1, 4] = 1,
        steps: app_commands.Range[int, 20, 50] = 25,
    ):
        if not _is_image_attachment(image_1):
            await interaction.response.send_message("⚠️ image_1 必須是圖片。", ephemeral=True)
            return
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
        source_bytes = await image_1.read()
        mark_bytes = await mark_image.read()
        if not source_bytes or not mark_bytes:
            await interaction.followup.send("⚠️ 原圖或 mark 圖為空，無法修正。", ephemeral=True)
            return

        # Keep temporary copies only for debugging/reproducibility on Zeabur persistent storage.
        run_tag = f"{interaction.id}_{uuid.uuid4().hex[:6]}"
        (_UPLOADS_DIR / f"{run_tag}_source{_ext(image_1)}").write_bytes(source_bytes)
        (_UPLOADS_DIR / f"{run_tag}_mark{_ext(mark_image)}").write_bytes(mark_bytes)

        try:
            await _run_fix(
                interaction,
                source_bytes=source_bytes,
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
        description="Qwen 2.1 局部修正：上傳原圖、mark 標註圖與 Delta",
        callback=qwen_fix_command,
    )
    command._params["image_1"].description = "原圖：要被局部修正的照片"
    command._params["mark_image"].description = "標註圖：在同一張圖上圈選/塗記要修的區域"
    command._params["delta"].description = "只描述標註區域要怎麼修改"
    command._params["count"].description = "候選張數（1~4）"
    command._params["steps"].description = "Qwen sampling steps（20~50）"
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
        "input_contract": "image1_plus_mark_image_plus_delta",
        "qwen_reference_policy": "image1_and_mark_only",
        "seedream_repair_unchanged": True,
    }
