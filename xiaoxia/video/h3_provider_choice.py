# -*- coding: utf-8 -*-
"""H3 provider chooser: fal.ai | RunPod | auto.

Installed late in the flat runtime so it only replaces the shared H3 button
interaction.  Existing fal.ai H3 generation stays untouched.

RunPod path:
- current image bytes are frame 1 / visual truth;
- Gemini H3 Director plan remains shared;
- Chinese model-facing continuation contract;
- open-weight MiniMax H3 FL2VA through RunPod worker-comfyui;
- first validation defaults to 5 seconds and ~480px short edge.

Auto means exactly: fal.ai first -> on final failure RunPod immediately.
There is no second confirmation.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Tuple

import aiohttp
import discord
from PIL import Image
import io

from xiaoxia.media import h3_runpod
from xiaoxia.video import diagnostics, h3, h3_director_mode, voiceover_mode
from xiaoxia.video.h3_provider_router import build_solo_continuation_contract


VERSION = "1.14.12-h3-provider-choice-v1"


def _env_int(name: str, default: int, minimum: int, maximum: int) -> int:
    try:
        value = int(str(os.environ.get(name, default)).strip())
    except Exception:
        value = default
    return max(minimum, min(maximum, value))


def _public_url(filename: str) -> str:
    base = (os.environ.get("XIAOXIA_PUBLIC_BASE_URL") or "https://xiaoxia0320.zeabur.app").rstrip("/")
    return f"{base}/gallery/{filename}"


async def _source_image_bytes(app: Any, context: Dict[str, Any]) -> bytes:
    ctx = context or {}
    local_path = str(ctx.get("local_path") or "").strip()
    if local_path and os.path.isfile(local_path):
        return Path(local_path).read_bytes()

    mapper = getattr(app, "_gallery_url_to_local_path", None)
    for key in ("local_url", "image_url"):
        value = str(ctx.get(key) or "").strip()
        if value and callable(mapper):
            try:
                mapped = mapper(value)
            except Exception:
                mapped = None
            if mapped and os.path.isfile(str(mapped)):
                return Path(str(mapped)).read_bytes()

    url = next(
        (
            str(ctx.get(key) or "").strip()
            for key in ("local_url", "image_url")
            if str(ctx.get(key) or "").strip().startswith(("http://", "https://"))
        ),
        "",
    )
    if not url:
        raise RuntimeError("H3_RUNPOD_SOURCE_IMAGE_NOT_FOUND")

    timeout = aiohttp.ClientTimeout(total=90)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url) as resp:
            if resp.status != 200:
                raise RuntimeError(f"H3_RUNPOD_SOURCE_HTTP_{resp.status}")
            return await resp.read()


def _dimensions(image_bytes: bytes) -> Tuple[int, int]:
    """Cheap first-pass baseline: preserve aspect ratio around a 480px short edge."""
    try:
        with Image.open(io.BytesIO(image_bytes)) as image:
            src_w, src_h = image.size
    except Exception:
        return 864, 480

    if src_w <= 0 or src_h <= 0:
        return 864, 480

    short = _env_int("H3_RUNPOD_SHORT_EDGE", 480, 320, 768)
    if src_w <= src_h:
        width = short
        height = round(short * src_h / src_w)
    else:
        height = short
        width = round(short * src_w / src_h)

    # Keep the first validation compact, and satisfy H3/ComfyUI's multiple-of-32 grid.
    long_cap = _env_int("H3_RUNPOD_LONG_EDGE_MAX", 864, 480, 1344)
    if max(width, height) > long_cap:
        scale = long_cap / max(width, height)
        width = round(width * scale)
        height = round(height * scale)

    width = max(320, round(width / 32) * 32)
    height = max(320, round(height / 32) * 32)
    return width, height


def _scene_text(app: Any, context: Dict[str, Any]) -> str:
    return h3._clean(
        app,
        context.get("authoritative_scene")
        or context.get("scene_summary")
        or context.get("scene_text")
        or context.get("composition")
        or context.get("message")
        or context.get("title")
        or "目前照片中的場景",
    )


def _is_scene_inheritance(context: Dict[str, Any]) -> bool:
    return bool(
        context.get("special_intimacy")
        or context.get("special_intimacy_parent_url")
        or context.get("trace_action") == "special_intimacy"
    )


def _runpod_prompt(app: Any, context: Dict[str, Any], plan: Dict[str, str]) -> str:
    scene = _scene_text(app, context)
    inherit = _is_scene_inheritance(context)
    contract = build_solo_continuation_contract(inherit_scene=inherit)

    parts = [
        "【影片任務】",
        "使用目前圖片作為影片第 1 幀與唯一視覺真實來源。",
        f"目前場景：{scene}",
        f"影片主題：{plan.get('video_theme') or '自然延續目前場景'}",
        f"主要動作：{plan.get('hero_action') or '自然地延續目前姿勢與動作'}",
        f"收尾反應：{plan.get('reaction') or '自然地看向鏡頭並收尾'}",
        f"鏡頭：{plan.get('camera') or '維持目前鏡頭，只做輕微自然運鏡'}",
        f"環境音：{plan.get('ambience') or '目前場景自然環境音'}",
        "",
        contract,
    ]

    voice = str(plan.get("voiceover") or "").strip()
    if voice:
        parts.extend([
            "",
            "【聲音】",
            "畫面中的小俠不開口、不對嘴；若生成旁白，旁白是完全離畫的內心旁白。",
            f"繁體中文畫外音：『{voice}』",
            "聲線自然、年輕、明亮、溫暖，不要播音腔；不要字幕，不要音樂。",
        ])
    return "\n".join(parts).strip()


def _write_runpod_trace(app: Any, payload: Dict[str, Any]) -> None:
    try:
        memory_dir = Path(str(getattr(app, "MEMORY_DIR", "") or "/data/memory"))
        base = memory_dir / "h3_trace"
        base.mkdir(parents=True, exist_ok=True)
        path = base / "latest_runpod.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as exc:
        print(f"⚠️ [H3_RUNPOD_TRACE_WRITE_FAILED] {type(exc).__name__}: {exc}")


async def _generate_runpod(app: Any, context: Dict[str, Any]) -> Dict[str, Any]:
    started = time.time()
    image_bytes = await _source_image_bytes(app, context)
    plan = await h3_director_mode.build_h3_director_plan(app, context, voiceover_mode._config())
    prompt = _runpod_prompt(app, context, plan)
    width, height = _dimensions(image_bytes)
    duration = _env_int("H3_RUNPOD_DURATION", 5, 4, 15)
    steps = _env_int("H3_RUNPOD_STEPS", 20, 4, 40)
    seed = int(time.time_ns() & 0x7FFFFFFF)

    trace = {
        "version": VERSION,
        "provider_requested": "runpod",
        "provider_final": "runpod",
        "h3_backend": "open_weights_comfyui",
        "checkpoint_family": "FL2VA",
        "source_image_sha256": hashlib.sha256(image_bytes).hexdigest(),
        "scene_inheritance": _is_scene_inheritance(context),
        "solo_subject_lock": True,
        "prompt": prompt,
        "duration_seconds": duration,
        "width": width,
        "height": height,
        "steps": steps,
        "status": "submitted",
    }
    _write_runpod_trace(app, trace)

    try:
        filename, video_bytes, meta = await h3_runpod.run_h3(
            image_bytes,
            prompt=prompt,
            duration_seconds=duration,
            width=width,
            height=height,
            steps=steps,
            seed=seed,
            timeout_seconds=float(os.environ.get("H3_RUNPOD_TIMEOUT_SECONDS") or 1200),
        )
        output_dir = Path(str(getattr(app, "OUTPUT_DIR", "") or "/tmp"))
        output_dir.mkdir(parents=True, exist_ok=True)
        suffix = Path(filename).suffix or ".mp4"
        local_name = f"xiaoxia_h3_runpod_{uuid.uuid4().hex[:10]}{suffix}"
        local_path = output_dir / local_name
        local_path.write_bytes(video_bytes)

        trace.update({
            "status": "completed",
            "elapsed_seconds": round(time.time() - started, 3),
            "runpod_job_id": meta.get("job_id"),
            "output_filename": local_name,
            "output_bytes": len(video_bytes),
            "meta": meta,
        })
        _write_runpod_trace(app, trace)

        context["h3_submitted_prompt"] = prompt
        context["h3_provider_final"] = "runpod"
        return {
            "model_id": meta.get("model") or "minimax-h3-fl2va-open-weights",
            "video_url": None,
            "local_path": str(local_path),
            "local_filename": local_name,
            "local_url": _public_url(local_name),
            "voice_script": str(plan.get("voiceover") or ""),
            "used_voice": bool(str(plan.get("voiceover") or "")),
            "voice_mode": "h3_open_weights_native_audio",
            "duration": duration,
            "resolution": f"{width}x{height}",
            "ambient_audio": True,
            "video_theme": plan.get("video_theme"),
            "motion_level": plan.get("motion_level"),
            "director_plan": plan,
            "submitted_prompt": prompt,
            "expanded_prompt": "",
            "provider_requested": "runpod",
            "provider_final": "runpod",
            "runpod_job_id": meta.get("job_id"),
            "h3_backend": "open_weights_comfyui",
        }
    except Exception as exc:
        trace.update({
            "status": "failed",
            "elapsed_seconds": round(time.time() - started, 3),
            "error_type": type(exc).__name__,
            "error": str(exc)[:3000],
        })
        _write_runpod_trace(app, trace)
        raise


async def _render_selected(app: Any, view: Any, interaction: discord.Interaction, provider: str) -> None:
    message_id = getattr(getattr(interaction, "message", None), "id", None)
    job_key = ("h3-provider", message_id or id(view))
    if job_key in h3._ACTIVE_JOBS:
        await interaction.response.send_message("🎬 這張照片正在生成 H3 影片，先等這一支完成喔。", ephemeral=True)
        return

    h3._ACTIVE_JOBS.add(job_key)
    await interaction.response.defer(thinking=True)
    context = dict(getattr(view, "context", {}) or {})

    try:
        if provider == "fal":
            result = await h3.generate_h3_video(app, context)
            result["provider_requested"] = "fal"
            result["provider_final"] = "fal"

        elif provider == "runpod":
            result = await _generate_runpod(app, context)

        elif provider == "auto":
            try:
                result = await h3.generate_h3_video(app, context)
                result["provider_requested"] = "auto"
                result["provider_attempted"] = ["fal"]
                result["provider_final"] = "fal"
                result["auto_fallback"] = False
            except Exception as fal_exc:
                print(f"⚠️ [H3_AUTO_FAL_FAILED] {type(fal_exc).__name__}: {fal_exc}")
                # Intentionally no confirmation here: this is the meaning of auto.
                result = await _generate_runpod(app, context)
                result["provider_requested"] = "auto"
                result["provider_attempted"] = ["fal", "runpod"]
                result["provider_final"] = "runpod"
                result["auto_fallback"] = True
                result["fal_failure_type"] = type(fal_exc).__name__
                result["fal_failure_message"] = str(fal_exc)[:1200]
        else:
            raise RuntimeError(f"Unsupported H3 provider: {provider}")

        context["h3_provider_requested"] = provider
        context["h3_provider_final"] = result.get("provider_final")
        view.context.update(context)
        await diagnostics._send_success_to_interaction(view, interaction, result)

    except Exception as exc:
        print(f"❌ [H3_PROVIDER_ERROR] provider={provider} {type(exc).__name__}: {exc!r}")
        await interaction.followup.send(
            f"⚠️ H3影片生成失敗（{provider}）：`{type(exc).__name__}: {str(exc)[:1200]}`",
            ephemeral=True,
        )
    finally:
        h3._ACTIVE_JOBS.discard(job_key)


class _ProviderButton(discord.ui.Button):
    def __init__(self, app: Any, owner_view: Any, provider: str, label: str, style: discord.ButtonStyle):
        super().__init__(label=label, style=style)
        self._app = app
        self._owner_view = owner_view
        self._provider = provider

    async def callback(self, interaction: discord.Interaction):
        await _render_selected(self._app, self._owner_view, interaction, self._provider)


class H3ProviderChoiceView(discord.ui.View):
    def __init__(self, app: Any, owner_view: Any):
        super().__init__(timeout=180)
        self.add_item(_ProviderButton(app, owner_view, "fal", "fal.ai", discord.ButtonStyle.secondary))
        self.add_item(_ProviderButton(app, owner_view, "runpod", "RunPod", discord.ButtonStyle.primary))
        self.add_item(_ProviderButton(app, owner_view, "auto", "自動", discord.ButtonStyle.success))


async def _provider_choice_callback(button: Any, interaction: discord.Interaction) -> None:
    app = button._app
    owner_view = button._owner_view

    runpod_ready = bool(
        os.environ.get("XIAOXIA_H3_RUNPOD_ENDPOINT_ID")
        and (
            os.environ.get("XIAOXIA_H3_RUNPOD_API_KEY")
            or os.environ.get("XIAOXIA_RUNPOD_SERVERLESS_API_KEY")
            or os.environ.get("RUNPOD_API_KEY")
        )
    )
    if not runpod_ready:
        await interaction.response.send_message(
            "⚠️ RunPod H3 尚未完成環境設定，目前只能使用 fal.ai。",
            ephemeral=True,
        )
        return

    await interaction.response.send_message(
        "🎬 選擇 H3 影片提供者：\n"
        "• **fal.ai**：只使用 fal.ai\n"
        "• **RunPod**：只使用開放權重 H3\n"
        "• **自動**：先 fal.ai，失敗後直接改 RunPod，不再詢問",
        view=H3ProviderChoiceView(app, owner_view),
        ephemeral=True,
    )


def install_h3_provider_choice(app: Any) -> Dict[str, Any]:
    if getattr(h3, "_xiaoxia_h3_provider_choice_installed", False):
        return {"version": VERSION, "patched": False, "reason": "already_installed"}

    async def patched_callback(self, interaction: discord.Interaction):
        await _provider_choice_callback(self, interaction)

    h3.H3VideoButton.callback = patched_callback
    app.h3_generate_runpod = lambda context: _generate_runpod(app, context)
    h3._xiaoxia_h3_provider_choice_installed = True

    return {
        "version": VERSION,
        "patched": True,
        "button": "🎬 H3影片生成",
        "providers": ["fal.ai", "RunPod", "自動"],
        "auto_contract": "fal.ai -> failure -> RunPod, no confirmation",
        "runpod_default_duration": _env_int("H3_RUNPOD_DURATION", 5, 4, 15),
        "runpod_trace": "/data/memory/h3_trace/latest_runpod.json",
        "scene_inheritance": True,
        "solo_subject_lock": True,
    }
