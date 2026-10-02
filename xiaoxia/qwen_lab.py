# -*- coding: utf-8 -*-
"""Temporary Qwen Image 2.1 reference sculpting lab for Xiaoxia."""
from __future__ import annotations

import json
import os
import secrets
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

import discord
from discord import app_commands

from xiaoxia.media.runpod_serverless import RunPodServerlessError, run_qwen21

VERSION = "1.14.11-qwen-lab-v1"

_ROOT = Path("/data/memory/qwen21")
_PROMPT_PATH = _ROOT / "lab_prompts.json"
_RUNS_DIR = _ROOT / "lab_runs"
_REFS_DIR = _ROOT / "refs"

_MODES = ("front_view", "45_view", "side_view", "full_view")
_MODE_TO_V2_REF = {
    "front_view": "image_5_body_half_front_v2.png",
    "45_view": "image_7_body_half_45_v2.png",
    "side_view": "image_8_body_half_90_v2.png",
    "full_view": "image_4_body_full_v2.png",
}

SYSTEM_CORE_PROMPT = """REFERENCE-ASSET LAB — FIXED CORE CONTRACT

<image1> is the only image to be edited and is the primary authority for the current subject, pose, framing, and continuity.

<image2>, <image3>, <image4>, <image5>, and <image6> are reference images of the SAME single 24-year-old adult woman shown in <image1>.
They are reference-only and must never appear as additional people or contribute extra body parts.

The final image must contain exactly ONE woman: the same woman from <image1>.

Use <image2> and <image3> only to preserve facial identity.
Use <image4> and <image5> only to preserve stable adult body proportions and anatomy.
Use <image6> only as an additional body-consistency reference.

Do not transfer pose, camera, background, lighting, clothing, or composition from the references unless the editable view template explicitly requests a view change.

Preserve Xiaoxia's youthful adult identity and recognizable face. Do not make her older, harsher, more glamorous, or like a different person.
Keep anatomy photorealistic and coherent. Avoid duplicate subjects, extra limbs, merged body parts, distorted hands or feet, plastic skin, waxy skin, and exaggerated anatomy.

This lab creates clean long-term body reference assets. The subject is an adult. The final reference image must be fully nude so body geometry and skin-tone references remain unobstructed. Remove clothing from <image1> while preserving the same woman.
"""

_DEFAULTS = {
    "system_base_prompt": """Create a clean, photorealistic Xiaoxia body-reference image suitable for long-term reuse by Qwen Image 2.1.

Keep the result neutral and reference-friendly rather than theatrical:
- natural skin texture and skin color
- balanced white balance
- soft, even, realistic light
- minimal background distraction
- no fashion styling, jewelry emphasis, props, text, watermark, or dramatic visual effects
- do not exaggerate any body feature unless the user delta explicitly requests a change
- preserve all features that the user delta does not ask to modify

The user delta is the only per-run change request. Apply it precisely while keeping unrelated anatomy and identity stable.""",
    "front_view": """Target reference view: front view.
Keep a clear, useful front-facing reference composition with a neutral body orientation toward the camera. Preserve the useful crop of <image1> unless the user delta specifically requests a different crop or framing.""",
    "45_view": """Target reference view: approximately 45-degree three-quarter view.
Create a clear three-quarter body reference that reveals depth and contour while remaining neutral and anatomically readable. Preserve the useful crop of <image1> unless the user delta specifically requests a different crop or framing.""",
    "side_view": """Target reference view: approximately 90-degree side profile.
Create a clear side-profile body reference that reveals projection, depth, and silhouette while remaining neutral and anatomically readable. Preserve the useful crop of <image1> unless the user delta specifically requests a different crop or framing.""",
    "full_view": """Target reference view: full-body reference.
Keep the entire body clearly visible from head to feet with natural standing proportions and minimal perspective distortion. Preserve Xiaoxia's established height impression, head-to-body ratio, torso, waist, hips, legs, hands, and feet unless the user delta explicitly requests a specific change."""
}


def _ensure_dirs() -> None:
    _ROOT.mkdir(parents=True, exist_ok=True)
    _RUNS_DIR.mkdir(parents=True, exist_ok=True)
    _REFS_DIR.mkdir(parents=True, exist_ok=True)


def _load_prompts() -> Dict[str, str]:
    _ensure_dirs()
    data = dict(_DEFAULTS)
    try:
        stored = json.loads(_PROMPT_PATH.read_text(encoding="utf-8"))
        if isinstance(stored, dict):
            for key in data:
                value = stored.get(key)
                if isinstance(value, str) and value.strip():
                    data[key] = value.strip()
    except Exception:
        pass
    return data


def _save_prompts(data: Dict[str, str]) -> None:
    _ensure_dirs()
    payload = {k: str(data.get(k) or _DEFAULTS[k]).strip() for k in _DEFAULTS}
    tmp = _PROMPT_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, _PROMPT_PATH)


def _effective_prompt(mode: str, delta: str) -> str:
    prompts = _load_prompts()
    return (
        SYSTEM_CORE_PROMPT.strip()
        + "\n\n"
        + prompts["system_base_prompt"].strip()
        + "\n\n"
        + prompts[mode].strip()
        + "\n\nUSER DELTA — apply this requested change precisely:\n"
        + (str(delta or "").strip() or "No additional change beyond producing a clean reference asset.")
    )


def _run_dir(run_id: str) -> Path:
    path = _RUNS_DIR / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_meta(run_id: str, data: Dict[str, Any]) -> None:
    (_run_dir(run_id) / "run.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _read_meta(run_id: str) -> Dict[str, Any]:
    try:
        value = json.loads((_run_dir(run_id) / "run.json").read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _image_ext(filename: str, content_type: str) -> str:
    lower = str(filename or "").lower()
    for ext in (".png", ".jpg", ".jpeg", ".webp"):
        if lower.endswith(ext):
            return ext
    return ".png" if "png" in str(content_type or "").lower() else ".jpg"


def _run_text(meta: Dict[str, Any], index: int, seed: int) -> str:
    delta = str(meta.get("delta") or "").replace("\n", " ").strip()
    if len(delta) > 450:
        delta = delta[:447] + "..."
    return (
        f"🧪 Qwen Lab | {meta.get('mode')}\n"
        f"Delta: {delta or '—'}\n"
        f"Steps: {meta.get('steps')} | Candidate: {index}/{meta.get('count')} | Seed: {seed}\n"
        f"Run: {meta.get('run_id')}"
    )


async def _generate_run(app: Any, interaction: discord.Interaction, source_path: Path, mode: str, delta: str, count: int, steps: int, parent_run_id: str = "") -> str:
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8]
    run_dir = _run_dir(run_id)
    source_copy = run_dir / ("source" + source_path.suffix.lower())
    shutil.copy2(source_path, source_copy)
    source_bytes = source_copy.read_bytes()
    prompt = _effective_prompt(mode, delta)

    meta = {
        "run_id": run_id,
        "created_at": datetime.now().astimezone().isoformat(),
        "mode": mode,
        "delta": delta,
        "steps": int(steps),
        "count": int(count),
        "source_path": str(source_copy),
        "parent_run_id": parent_run_id,
        "effective_prompt": prompt,
        "outputs": [],
    }
    _write_meta(run_id, meta)

    status = await interaction.followup.send(f"🧪 Qwen Lab: {mode} 正在產生 {count} 張候選圖...", wait=True)
    completed = 0
    try:
        for index in range(1, int(count) + 1):
            seed = secrets.randbelow(2**63 - 1)
            results = await run_qwen21(source_bytes, prompt=prompt, seed=seed, steps=int(steps))
            if not results:
                raise RunPodServerlessError(f"candidate {index} returned no image")
            _, blob = results[0]
            out_path = run_dir / f"candidate_{index}.png"
            out_path.write_bytes(blob)
            meta["outputs"].append({"index": index, "seed": seed, "path": str(out_path), "bytes": len(blob)})
            _write_meta(run_id, meta)
            view = LabCandidateView(app, run_id, out_path, getattr(interaction.user, "id", None))
            await interaction.followup.send(_run_text(meta, index, seed), file=discord.File(str(out_path), filename=out_path.name), view=view)
            completed += 1
            try:
                await status.edit(content=f"🧪 Qwen Lab: 已完成 {completed}/{count} 張...")
            except Exception:
                pass
    finally:
        try:
            await status.delete()
        except Exception:
            pass
    print(f"✅ [QWEN_LAB_RUN] version={VERSION} run_id={run_id} mode={mode} count={completed}/{count} steps={steps}")
    return run_id


class DeltaModal(discord.ui.Modal):
    def __init__(self, app: Any, run_id: str, source_path: Path, title: str, initial: str, owner_id: int | None):
        super().__init__(title=title[:45], timeout=600)
        self.app = app
        self.run_id = run_id
        self.source_path = source_path
        self.owner_id = owner_id
        self.delta_input = discord.ui.TextInput(label="這一輪要調整的部分", style=discord.TextStyle.paragraph, default=str(initial or "")[:4000], required=False, max_length=4000)
        self.add_item(self.delta_input)

    async def on_submit(self, interaction: discord.Interaction):
        if self.owner_id is not None and interaction.user.id != self.owner_id:
            await interaction.response.send_message("這是大俠目前的 Qwen Lab 操作。", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        meta = _read_meta(self.run_id)
        await _generate_run(self.app, interaction, self.source_path, str(meta.get("mode") or "front_view"), str(self.delta_input.value or "").strip(), int(meta.get("count") or 4), int(meta.get("steps") or 25), self.run_id)


class ConfirmAdoptView(discord.ui.View):
    def __init__(self, run_id: str, candidate_path: Path, owner_id: int | None):
        super().__init__(timeout=300)
        self.run_id = run_id
        self.candidate_path = candidate_path
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.owner_id is not None and interaction.user.id != self.owner_id:
            await interaction.response.send_message("這是大俠目前的 Qwen Lab 操作。", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="確認採用", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        meta = _read_meta(self.run_id)
        mode = str(meta.get("mode") or "")
        filename = _MODE_TO_V2_REF.get(mode)
        if not filename:
            await interaction.response.send_message("⚠️ 找不到這個 mode 的 v2 底圖位置。", ephemeral=True)
            return
        target = _REFS_DIR / filename
        backup = None
        if target.exists():
            backup = target.with_name(target.stem + "_previous" + target.suffix)
            shutil.copy2(target, backup)
        shutil.copy2(self.candidate_path, target)
        text = f"✅ 已採用為 {mode} 的 qwen2.1_special_v2 底圖：{target.name}"
        if backup:
            text += f"\n上一版備份：{backup.name}"
        await interaction.response.edit_message(content=text, view=None)
        print(f"✅ [QWEN_LAB_ADOPT] mode={mode} source={self.candidate_path} target={target}")

    @discord.ui.button(label="取消", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.edit_message(content="已取消採用。", view=None)


class LabCandidateView(discord.ui.View):
    def __init__(self, app: Any, run_id: str, candidate_path: Path, owner_id: int | None):
        super().__init__(timeout=1800)
        self.app = app
        self.run_id = run_id
        self.candidate_path = candidate_path
        self.owner_id = owner_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.owner_id is not None and interaction.user.id != self.owner_id:
            await interaction.response.send_message("這是大俠目前的 Qwen Lab 操作。", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="用此圖續修", style=discord.ButtonStyle.primary, row=0)
    async def refine(self, interaction: discord.Interaction, button: discord.ui.Button):
        meta = _read_meta(self.run_id)
        await interaction.response.send_modal(DeltaModal(self.app, self.run_id, self.candidate_path, "用此圖續修", str(meta.get("delta") or ""), self.owner_id))

    @discord.ui.button(label="同條件再生4張", style=discord.ButtonStyle.secondary, row=0)
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        meta = _read_meta(self.run_id)
        source = Path(str(meta.get("source_path") or ""))
        if not source.is_file():
            await interaction.followup.send("⚠️ 找不到這一輪原始 image_1。", ephemeral=True)
            return
        await _generate_run(self.app, interaction, source, str(meta.get("mode") or "front_view"), str(meta.get("delta") or ""), 4, int(meta.get("steps") or 25), self.run_id)

    @discord.ui.button(label="修改提示詞重跑", style=discord.ButtonStyle.secondary, row=1)
    async def reprompt(self, interaction: discord.Interaction, button: discord.ui.Button):
        meta = _read_meta(self.run_id)
        source = Path(str(meta.get("source_path") or ""))
        if not source.is_file():
            await interaction.response.send_message("⚠️ 找不到這一輪原始 image_1。", ephemeral=True)
            return
        await interaction.response.send_modal(DeltaModal(self.app, self.run_id, source, "修改 Delta 後重跑", str(meta.get("delta") or ""), self.owner_id))

    @discord.ui.button(label="採用為 v2 底圖", style=discord.ButtonStyle.success, row=1)
    async def adopt(self, interaction: discord.Interaction, button: discord.ui.Button):
        meta = _read_meta(self.run_id)
        mode = str(meta.get("mode") or "")
        await interaction.response.send_message(
            f"要把這張採用為 {mode} 的正式 v2 底圖 {_MODE_TO_V2_REF.get(mode, '?')} 嗎？",
            view=ConfirmAdoptView(self.run_id, self.candidate_path, self.owner_id),
            ephemeral=True,
        )


class PromptEditModal(discord.ui.Modal):
    def __init__(self, key: str, current: str):
        titles = {"system_base_prompt": "修改 SYSTEM_BASE_PROMPT", "front_view": "修改 front_view", "45_view": "修改 45_view", "side_view": "修改 side_view", "full_view": "修改 full_view"}
        super().__init__(title=titles[key][:45], timeout=600)
        self.key = key
        self.body = discord.ui.TextInput(label=key, style=discord.TextStyle.paragraph, default=str(current or "")[:4000], required=True, max_length=4000)
        self.add_item(self.body)

    async def on_submit(self, interaction: discord.Interaction):
        data = _load_prompts()
        data[self.key] = str(self.body.value or "").strip()
        _save_prompts(data)
        await interaction.response.send_message(f"✅ 已更新 {self.key}。下一次 Qwen Lab 立即生效，不需 redeploy。", ephemeral=True)


class PromptKeyButton(discord.ui.Button):
    def __init__(self, key: str, label: str, row: int):
        super().__init__(label=label, style=discord.ButtonStyle.secondary, row=row)
        self.key = key

    async def callback(self, interaction: discord.Interaction):
        data = _load_prompts()
        await interaction.response.send_modal(PromptEditModal(self.key, data[self.key]))


class PromptEditorView(discord.ui.View):
    def __init__(self, owner_id: int | None):
        super().__init__(timeout=900)
        self.owner_id = owner_id
        for key, label, row in (("system_base_prompt", "SYSTEM_BASE_PROMPT", 0), ("front_view", "front_view", 0), ("45_view", "45_view", 0), ("side_view", "side_view", 1), ("full_view", "full_view", 1)):
            self.add_item(PromptKeyButton(key, label, row))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.owner_id is not None and interaction.user.id != self.owner_id:
            await interaction.response.send_message("這是大俠目前的 Qwen Lab Prompt 編輯器。", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="查看目前組裝結果", style=discord.ButtonStyle.primary, row=2)
    async def preview(self, interaction: discord.Interaction, button: discord.ui.Button):
        data = _load_prompts()
        text = "SYSTEM_CORE_PROMPT（固定不可編輯）\n" + SYSTEM_CORE_PROMPT.strip() + "\n\nSYSTEM_BASE_PROMPT\n" + data["system_base_prompt"] + "\n\n" + "\n\n".join(f"[{mode}]\n{data[mode]}" for mode in _MODES)
        chunks = [text[i:i+1800] for i in range(0, len(text), 1800)]
        await interaction.response.send_message(chunks[0], ephemeral=True)
        for chunk in chunks[1:]:
            await interaction.followup.send(chunk, ephemeral=True)

    @discord.ui.button(label="還原預設", style=discord.ButtonStyle.danger, row=2)
    async def reset(self, interaction: discord.Interaction, button: discord.ui.Button):
        _save_prompts(dict(_DEFAULTS))
        await interaction.response.send_message("✅ 已還原 SYSTEM_BASE_PROMPT 與 4 個 view templates。", ephemeral=True)


def install_qwen_lab(app: Any) -> Dict[str, Any]:
    bot = app.girlfriend_bot
    tree = bot.tree
    group = app_commands.Group(name="qwen_lab", description="Qwen Image 2.1 小俠底圖雕塑工具")

    @group.command(name="提示詞", description="上傳 image_1，輸入 Delta，產生底圖候選")
    @app_commands.describe(image_1="這一輪要修改的主圖", mode="目標參考視角", delta="只寫這一輪想修改的部分", count="一次產生幾張候選圖", steps="Qwen sampling steps")
    @app_commands.choices(mode=[
        app_commands.Choice(name="正面 front_view", value="front_view"),
        app_commands.Choice(name="45度 45_view", value="45_view"),
        app_commands.Choice(name="側面 side_view", value="side_view"),
        app_commands.Choice(name="全身 full_view", value="full_view"),
    ])
    async def generate(interaction: discord.Interaction, image_1: discord.Attachment, mode: app_commands.Choice[str], delta: str = "", count: app_commands.Range[int, 1, 4] = 4, steps: app_commands.Range[int, 20, 50] = 25):
        content_type = str(image_1.content_type or "").lower()
        filename = str(image_1.filename or "")
        if not (content_type.startswith("image/") or filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp"))):
            await interaction.response.send_message("⚠️ image_1 必須是圖片。", ephemeral=True)
            return
        if not os.environ.get("XIAOXIA_RUNPOD_SERVERLESS_ENDPOINT_ID") or not (os.environ.get("XIAOXIA_RUNPOD_SERVERLESS_API_KEY") or os.environ.get("RUNPOD_API_KEY")):
            await interaction.response.send_message("⚠️ RunPod Qwen21 Serverless 尚未設定。", ephemeral=True)
            return
        await interaction.response.defer(thinking=True)
        upload_dir = _RUNS_DIR / "_uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        source = upload_dir / f"upload_{interaction.id}_{uuid.uuid4().hex[:6]}{_image_ext(filename, content_type)}"
        source.write_bytes(await image_1.read())
        await _generate_run(app, interaction, source, str(mode.value), str(delta or "").strip(), int(count), int(steps))

    @group.command(name="修改提示詞", description="修改 Qwen Lab 固定 Prompt")
    async def prompts(interaction: discord.Interaction):
        _ensure_dirs()
        if not _PROMPT_PATH.exists():
            _save_prompts(dict(_DEFAULTS))
        await interaction.response.send_message("🧪 Qwen Lab Prompt 編輯器\nSYSTEM_CORE_PROMPT 固定不開放修改；Base / View 修改後立即生效。", view=PromptEditorView(getattr(interaction.user, "id", None)), ephemeral=True)

    tree.add_command(group, override=True)
    original_ready = getattr(bot, "on_ready", None)
    synced = False

    async def on_ready_with_qwen_lab_sync():
        nonlocal synced
        if original_ready is not None:
            await original_ready()
        if synced:
            return
        try:
            synced_cmds = await tree.sync()
            synced = True
            print(f"✅ [QWEN_LAB_SLASH_SYNC] version={VERSION} synced={len(synced_cmds)}")
        except Exception as exc:
            print(f"❌ [QWEN_LAB_SLASH_SYNC_FAILED] {type(exc).__name__}: {exc}")

    bot.on_ready = on_ready_with_qwen_lab_sync
    return {"version": VERSION, "group": "qwen_lab", "commands": ["提示詞", "修改提示詞"], "modes": list(_MODES), "default_count": 4, "prompt_storage": str(_PROMPT_PATH), "v2_refs": dict(_MODE_TO_V2_REF)}
