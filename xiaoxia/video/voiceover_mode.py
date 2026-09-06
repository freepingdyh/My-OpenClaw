# -*- coding: utf-8 -*-
"""v1.12.06h — Xiaoxia H3 voiceover mode.

Default experience:
- 10-second H3 clip;
- Xiaoxia does NOT speak on camera: no lip-sync, mouth stays relaxed/mostly closed;
- H3 generates natural scene ambience (waves, gulls, cafe noise, room tone, etc.);
- Gemini TTS / Sulafat produces an off-screen inner-monologue voiceover;
- ffmpeg mixes Sulafat over H3 ambience;
- if Sulafat TTS is unavailable, fall back once to H3 native off-screen narration;
- if that also fails, return ambient-only H3 video.
"""
from __future__ import annotations

import asyncio
import os
import shutil
import uuid
from typing import Any, Dict, Optional

import discord
from google.genai import types

from xiaoxia.video import h3, diagnostics, legacy_command


_ORIGINAL_CONFIG = h3._config


def _config() -> Dict[str, Any]:
    cfg = dict(_ORIGINAL_CONFIG())
    if "H3_VIDEO_DURATION" not in os.environ:
        cfg["duration"] = 10
    cfg["voice_mode"] = "voiceover_sulafat"
    return cfg


def _scene(app: Any, context: Dict[str, Any]) -> str:
    return h3._scene_text(app, context)


def _mode(context: Dict[str, Any]) -> str:
    return h3._mode(context)


async def _build_inner_monologue(app: Any, context: Dict[str, Any], cfg: Dict[str, Any]) -> str:
    scene = _scene(app, context)
    title = h3._clean(app, context.get("title") or context.get("activity_title") or "")
    message = h3._clean(app, context.get("message") or "")
    prompt = f"""妳是小俠 10 秒短影片的內心旁白編劇。
只輸出繁體中文旁白本身，不要標題、括號、動作說明或 emoji。
長度約 18～32 個中文字，1～2 句，10 秒內自然說完。
這是『內心戲／畫外音』，畫面中的小俠不開口。
語氣是 24 歲台灣女生：年輕、活潑、明亮、自然，帶一點磁性與溫柔感；不要播音腔、不要誇張演戲。
內容必須緊扣目前畫面，可以自然稱呼大俠。
模式：{_mode(context)}
標題：{title}
場景：{scene}
補充：{message}
"""
    resp = await app.gemini_client.aio.models.generate_content(model=cfg["script_model"], contents=prompt)
    text = h3._clean(app, getattr(resp, "text", "") or "").strip('"').strip("「」").strip()
    return (text or "大俠，我沒有說出口，但這一刻其實一直想著你。")[:96]


async def _tts_sulafat_voiceover(app: Any, script: str, cfg: Dict[str, Any]) -> str:
    tts_prompt = (
        "請用自然的台灣國語朗讀以下旁白。聲音設定：24 歲台灣女生，年輕、活潑、明亮，"
        "帶一點磁性與溫柔感；有輕微笑意，但不要撒嬌、不要播音腔、不要舞台式表演。"
        "語速自然偏輕快，清楚但像真實生活中的內心旁白。不要自行增刪內容。\n"
        "【旁白】\n" + script
    )
    tts_cfg = types.GenerateContentConfig(
        response_modalities=["AUDIO"],
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=cfg["tts_voice"])
            )
        ),
    )
    resp = await app.gemini_client.aio.models.generate_content(
        model=cfg["tts_model"], contents=[tts_prompt], config=tts_cfg
    )
    pcm = resp.candidates[0].content.parts[0].inline_data.data
    wav_path = os.path.join("/tmp", f"xiaoxia_vo_{uuid.uuid4().hex[:8]}.wav")
    import wave
    with wave.open(wav_path, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(24000)
        wav.writeframes(pcm)
    return wav_path


def _ambient_prompt(app: Any, context: Dict[str, Any], *, minimal: bool = False) -> str:
    scene = _scene(app, context)
    if minimal:
        return (
            "Animate the same person from the source image with subtle natural motion. "
            "Keep the same face, hairstyle, clothing, body proportions, camera view and location. "
            "Her mouth stays relaxed and mostly closed; she is not speaking. "
            "Use only small realistic movements: blinking, breathing, slight eye movement, tiny head movement, and gentle hair or fabric motion. "
            "Avoid exaggerated facial expressions, wide mouth movement, strong jaw motion, neck strain, or dramatic acting. "
            "Generate natural scene ambience only, with no dialogue and no music."
        )
    return (
        "Animate the source image as the same Xiaoxia, prioritizing identity preservation over dramatic motion. "
        "Keep her facial geometry, eyes, nose, jawline, neck, hairstyle, outfit, body proportions, camera framing and environment consistent with the still image. "
        "She does not speak on camera: keep her mouth relaxed and mostly closed. "
        "Use restrained realistic motion only: natural breathing, blinking, subtle eye shifts, very small head movement, and gentle hair/fabric movement appropriate to the existing pose. "
        "No exaggerated smile, no wide mouth opening, no theatrical expression, no pronounced facial or neck muscle tension, and no large pose change. "
        "Do not add people, text, subtitles, logos, or change the location. "
        "Generate natural diegetic ambience matching the scene, such as wind, waves, gulls, cafe room tone, street ambience, or quiet indoor sound as appropriate. No dialogue and no music. "
        f"Scene anchor: {scene}"
    )


def _native_voiceover_prompt(app: Any, context: Dict[str, Any], script: str) -> str:
    return (
        _ambient_prompt(app, context, minimal=True) + " "
        "Add an off-screen female voice-over narration in Traditional Chinese. "
        "The woman visible in the image must NOT lip-sync and must not appear to speak; her mouth stays relaxed. "
        f"Voice-over line: {script}"
    )


async def _subscribe(app: Any, model_id: str, arguments: Dict[str, Any], tag: str) -> Dict[str, Any]:
    fal_client = app._get_fal_client()
    def run():
        def on_queue_update(update):
            try:
                if isinstance(update, fal_client.InProgress):
                    for log in update.logs:
                        print(f"🎬 [{tag}] {log.get('message', '')}")
            except Exception:
                pass
        return fal_client.subscribe(model_id, arguments=arguments, with_logs=True, on_queue_update=on_queue_update)
    return await asyncio.to_thread(run)


async def _render_h3(app: Any, context: Dict[str, Any], cfg: Dict[str, Any], prompt: str) -> Dict[str, Any]:
    image_url = await h3._ensure_image_url(app, context)
    model_id = cfg["image_model"]
    args = {
        "prompt": prompt,
        "duration": cfg["duration"],
        "resolution": cfg["resolution"],
        "enable_safety_checker": cfg["safety"],
        "prompt_expansion_mode": cfg["expansion"],
        "image_url": image_url,
    }
    try:
        result = await _subscribe(app, model_id, args, "H3_VOICEOVER_AMBIENCE_QUEUE")
    except Exception as exc:
        info = diagnostics.extract_h3_error(exc)
        if str(info.get("type") or "").lower() == "content_policy_violation" and str(info.get("loc") or "").lower() == "body.prompt":
            args["prompt"] = _ambient_prompt(app, context, minimal=True)
            result = await _subscribe(app, model_id, args, "H3_VOICEOVER_MINIMAL_QUEUE")
        else:
            raise
    video = result.get("video") if isinstance(result, dict) else None
    url = video.get("url") if isinstance(video, dict) else None
    if not url:
        raise RuntimeError(f"H3_VOICEOVER_NO_URL: {result}")
    path, filename, public = await h3._download_video(app, url)
    if not path:
        raise RuntimeError("H3_VOICEOVER_DOWNLOAD_FAILED")
    return {"model_id": model_id, "video_url": url, "local_path": path, "local_filename": filename, "local_url": public}


async def _mix_voiceover(video_path: str, voice_path: str, duration: int) -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFMPEG_NOT_FOUND")
    out = os.path.splitext(video_path)[0] + "_voiceover.mp4"
    # Prefer H3's own ambient track at low volume; overlay Sulafat after a short natural lead-in.
    cmd = [
        ffmpeg, "-y", "-i", video_path, "-i", voice_path,
        "-filter_complex",
        "[0:a]volume=0.38[amb];[1:a]adelay=350|350,volume=1.0[vo];[amb][vo]amix=inputs=2:duration=first:dropout_transition=2[a]",
        "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-t", str(duration), out,
    ]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
    _, err = await proc.communicate()
    if proc.returncode != 0:
        # Some H3 outputs may have no audio stream. In that case keep Sulafat only.
        cmd2 = [
            ffmpeg, "-y", "-i", video_path, "-i", voice_path,
            "-filter_complex", "[1:a]adelay=350|350,volume=1.0[a]",
            "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "160k", "-t", str(duration), out,
        ]
        proc2 = await asyncio.create_subprocess_exec(*cmd2, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE)
        _, err2 = await proc2.communicate()
        if proc2.returncode != 0:
            raise RuntimeError(f"FFMPEG_MIX_FAILED: {(err2 or err)[-500:].decode(errors='ignore')}")
    return out


async def _native_voiceover_fallback(app: Any, context: Dict[str, Any], cfg: Dict[str, Any], script: str) -> Dict[str, Any]:
    image_url = await h3._ensure_image_url(app, context)
    model_id = cfg["image_model"]
    args = {
        "prompt": _native_voiceover_prompt(app, context, script),
        "duration": cfg["duration"],
        "resolution": cfg["resolution"],
        "enable_safety_checker": cfg["safety"],
        "prompt_expansion_mode": cfg["expansion"],
        "image_url": image_url,
    }
    result = await _subscribe(app, model_id, args, "H3_NATIVE_VOICEOVER_QUEUE")
    video = result.get("video") if isinstance(result, dict) else None
    url = video.get("url") if isinstance(video, dict) else None
    if not url:
        raise RuntimeError(f"H3_NATIVE_VOICEOVER_NO_URL: {result}")
    path, filename, public = await h3._download_video(app, url)
    return {
        "model_id": model_id, "video_url": url, "local_path": path, "local_filename": filename, "local_url": public,
        "voice_script": script, "used_voice": True, "voice_mode": "voiceover_h3",
        "duration": cfg["duration"], "resolution": cfg["resolution"], "ambient_audio": True,
    }


async def generate_voiceover_video(app: Any, context: Dict[str, Any]) -> Dict[str, Any]:
    cfg = _config()
    script = await _build_inner_monologue(app, context, cfg)
    voice_path: Optional[str] = None
    try:
        try:
            voice_path = await _tts_sulafat_voiceover(app, script, cfg)
        except Exception as tts_exc:
            print(f"⚠️ [SULAFAT_VOICEOVER_FAILED] {type(tts_exc).__name__}: {tts_exc}")
            try:
                return await _native_voiceover_fallback(app, context, cfg, script)
            except Exception as native_exc:
                print(f"⚠️ [H3_NATIVE_VOICEOVER_FAILED] {type(native_exc).__name__}: {native_exc}")
                base = await _render_h3(app, context, cfg, _ambient_prompt(app, context))
                base.update({"voice_script": "", "used_voice": False, "voice_mode": "ambient_only", "duration": cfg["duration"], "resolution": cfg["resolution"], "ambient_audio": True})
                return base

        base = await _render_h3(app, context, cfg, _ambient_prompt(app, context))
        mixed = await _mix_voiceover(base["local_path"], voice_path, cfg["duration"])
        # Publish mixed file in the existing gallery directory.
        final_name = os.path.basename(mixed)
        final_public = f"https://xiaoxia0320.zeabur.app/gallery/{final_name}"
        return {
            **base,
            "local_path": mixed,
            "local_filename": final_name,
            "local_url": final_public,
            "voice_script": script,
            "used_voice": True,
            "voice_mode": "voiceover_sulafat",
            "duration": cfg["duration"],
            "resolution": cfg["resolution"],
            "ambient_audio": True,
        }
    finally:
        if voice_path and os.path.exists(voice_path):
            try:
                os.remove(voice_path)
            except Exception:
                pass


async def _send_success_interaction(view, interaction: discord.Interaction, result: Dict[str, Any]) -> None:
    cfg = _config()
    lines = ["🎬 **H3影片生成完成**", f"規格：{result.get('duration')} 秒｜{result.get('resolution')}"]
    mode = result.get("voice_mode")
    if mode == "voiceover_sulafat":
        lines.append(f"🎙️ Sulafat 內心旁白：{result.get('voice_script')}")
        if result.get("ambient_audio"):
            lines.append("🌿 H3 場景環境音")
    elif mode == "voiceover_h3":
        lines.append(f"🎙️ H3 原生旁白（fallback）：{result.get('voice_script')}")
    elif mode == "ambient_only":
        lines.append("🌿 本次只有 H3 場景環境音（語音 fallback 未成功）")
    path = str(result.get("local_path") or "")
    max_bytes = int(cfg.get("send_file_max_mb") or 24) * 1024 * 1024
    if path and os.path.exists(path) and os.path.getsize(path) <= max_bytes:
        await interaction.followup.send("\n".join(lines), file=discord.File(path, filename=os.path.basename(path)))
    else:
        link = result.get("local_url") or result.get("video_url")
        if link:
            lines.append(f"📎 {link}")
        await interaction.followup.send("\n".join(lines))
    view.context["last_h3_video_url"] = result.get("local_url") or result.get("video_url")
    view.context["last_h3_video_model_id"] = result.get("model_id")
    view.context["last_h3_voice_script"] = result.get("voice_script") or ""


async def _send_success_ctx(ctx, result: Dict[str, Any]) -> None:
    cfg = _config()
    lines = ["🎬 **H3影片生成完成**", f"規格：{result.get('duration')} 秒｜{result.get('resolution')}"]
    mode = result.get("voice_mode")
    if mode == "voiceover_sulafat":
        lines.append(f"🎙️ Sulafat 內心旁白：{result.get('voice_script')}")
        lines.append("🌿 H3 場景環境音")
    elif mode == "voiceover_h3":
        lines.append(f"🎙️ H3 原生旁白（fallback）：{result.get('voice_script')}")
    elif mode == "ambient_only":
        lines.append("🌿 本次只有 H3 場景環境音")
    path = str(result.get("local_path") or "")
    max_bytes = int(cfg.get("send_file_max_mb") or 24) * 1024 * 1024
    if path and os.path.exists(path) and os.path.getsize(path) <= max_bytes:
        await ctx.reply("\n".join(lines), file=discord.File(path, filename=os.path.basename(path)), mention_author=False)
    else:
        link = result.get("local_url") or result.get("video_url")
        if link:
            lines.append(f"📎 {link}")
        await ctx.reply("\n".join(lines), mention_author=False)


def install_voiceover_mode(app: Any) -> Dict[str, Any]:
    h3._config = _config
    diagnostics.h3._config = _config
    legacy_command._config = _config
    h3.generate_h3_video = generate_voiceover_video
    app.generate_h3_video_from_context = lambda context: generate_voiceover_video(app, context)
    diagnostics._send_success_to_interaction = _send_success_interaction
    legacy_command._send_video_result = _send_success_ctx
    return {
        "patched": True,
        "duration_default": _config().get("duration"),
        "primary_voice": "Sulafat off-screen inner monologue",
        "fallback_voice": "H3 native off-screen narration",
        "visual_rule": "subject does not speak; identity-preserving subtle motion",
        "ambient_audio": "H3 scene-matched ambience",
    }
