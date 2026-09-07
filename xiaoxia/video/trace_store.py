# -*- coding: utf-8 -*-
"""v1.12.06i — persistent H3 request/response trace for Xiaoxia.

Purpose:
- record exactly what was sent to fal H3 on every attempt;
- distinguish prompt / image_url / reference_audio moderation without guessing;
- prove whether two attempts really used the same image bytes via SHA-256;
- preserve success/failure history under /data/memory/h3_trace.

Files:
  /data/memory/h3_trace/h3_trace.jsonl
  /data/memory/h3_trace/latest.json
  /data/memory/h3_trace/failed/<trace_id>.json
"""
from __future__ import annotations

import asyncio
import contextvars
import hashlib
import json
import os
import re
import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional

import aiohttp

from xiaoxia.video import h3, diagnostics, voiceover_mode


_TPE = timezone(timedelta(hours=8))
_TRACE_CTX: contextvars.ContextVar[Optional[Dict[str, Any]]] = contextvars.ContextVar("xiaoxia_h3_trace", default=None)
_ORIGINAL_SUBSCRIBE = voiceover_mode._subscribe
_ORIGINAL_BUILD_MONOLOGUE = voiceover_mode._build_inner_monologue
_ORIGINAL_TTS = voiceover_mode._tts_sulafat_voiceover
_ORIGINAL_GENERATE = voiceover_mode.generate_voiceover_video
_ORIGINAL_FORMAT_ERROR = diagnostics.format_h3_error


def _now() -> str:
    return datetime.now(_TPE).strftime("%Y-%m-%d %H:%M:%S")


def _safe(value: Any, depth: int = 0) -> Any:
    if depth > 6:
        return str(value)[:1000]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        return value if len(value) <= 12000 else value[:12000] + "…[TRUNCATED]"
    if isinstance(value, dict):
        return {str(k): _safe(v, depth + 1) for k, v in list(value.items())[:160]}
    if isinstance(value, (list, tuple)):
        return [_safe(v, depth + 1) for v in list(value)[:160]]
    return str(value)[:2000]


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_text(text: Any) -> str:
    return hashlib.sha256(str(text or "").encode("utf-8", errors="replace")).hexdigest()


def _file_info(path: Optional[str]) -> Dict[str, Any]:
    if not path:
        return {"path": None, "exists": False, "size": None, "sha256": None}
    try:
        if not os.path.isfile(path):
            return {"path": path, "exists": False, "size": None, "sha256": None}
        h = hashlib.sha256()
        size = 0
        with open(path, "rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                size += len(chunk)
                h.update(chunk)
        return {"path": path, "exists": True, "size": size, "sha256": h.hexdigest()}
    except Exception as exc:
        return {"path": path, "exists": False, "size": None, "sha256": None, "hash_error": f"{type(exc).__name__}: {exc}"}


def _paths(app: Any) -> Dict[str, str]:
    memory_dir = str(getattr(app, "MEMORY_DIR", "") or "/data/memory")
    base = os.path.join(memory_dir, "h3_trace")
    failed = os.path.join(base, "failed")
    os.makedirs(failed, exist_ok=True)
    return {
        "base": base,
        "jsonl": os.path.join(base, "h3_trace.jsonl"),
        "latest": os.path.join(base, "latest.json"),
        "failed": failed,
    }


def _write_jsonl(app: Any, trace: Dict[str, Any]) -> None:
    try:
        paths = _paths(app)
        payload = _safe(trace)
        with open(paths["jsonl"], "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
        latest = {}
        try:
            if os.path.exists(paths["latest"]):
                with open(paths["latest"], "r", encoding="utf-8") as f:
                    latest = json.load(f)
                if not isinstance(latest, dict):
                    latest = {}
        except Exception:
            latest = {}
        latest["last"] = payload
        latest[str(trace.get("module") or "h3")] = payload
        with open(paths["latest"], "w", encoding="utf-8") as f:
            json.dump(latest, f, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"⚠️ [H3_TRACE_WRITE_FAILED] {type(exc).__name__}: {exc}")


def _write_failed(app: Any, trace: Dict[str, Any]) -> None:
    try:
        path = os.path.join(_paths(app)["failed"], f"{trace.get('trace_id')}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(_safe(trace), f, ensure_ascii=False, indent=2)
    except Exception as exc:
        print(f"⚠️ [H3_TRACE_FAILED_SNAPSHOT_ERROR] {type(exc).__name__}: {exc}")


def _stage(app: Any, trace: Dict[str, Any], stage: str, data: Optional[Dict[str, Any]] = None, *, snapshot: bool = False) -> None:
    trace["updated_at"] = _now()
    trace.setdefault("stages", []).append({"time": _now(), "stage": stage, "data": _safe(data or {})})
    if len(trace["stages"]) > 80:
        del trace["stages"][:-80]
    if snapshot:
        _write_jsonl(app, trace)


def _mode(context: Dict[str, Any]) -> str:
    try:
        return h3._mode(context)
    except Exception:
        return str(context.get("source_mode") or context.get("type") or "unknown")


def _new_trace(app: Any, context: Dict[str, Any]) -> Dict[str, Any]:
    cfg = voiceover_mode._config()
    module = _mode(context)
    local_path = str(context.get("local_path") or "").strip() or None
    source_url = str(context.get("local_url") or context.get("image_url") or "").strip() or None
    local_info = _file_info(local_path)
    return {
        "trace_id": f"h3_{datetime.now(_TPE).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}",
        "created_at": _now(),
        "updated_at": _now(),
        "module": module,
        "source_mode": context.get("source_mode"),
        "context_trace_id": context.get("trace_id"),
        "title": context.get("title") or context.get("activity_title"),
        "scene_summary": context.get("authoritative_scene") or context.get("scene_summary") or context.get("scene_text"),
        "source_image_url": source_url,
        "source_image_local": local_info,
        "duration_sec": cfg.get("duration"),
        "resolution": cfg.get("resolution"),
        "safety_checker": cfg.get("safety"),
        "voice_mode": cfg.get("voice_mode"),
        "tts_model": cfg.get("tts_model"),
        "tts_voice": cfg.get("tts_voice"),
        "image_model": cfg.get("image_model"),
        "reference_model": cfg.get("reference_model"),
        "result": "pending",
        "attempt_count": 0,
        "stages": [],
    }


async def _remote_hash(url: Optional[str]) -> Dict[str, Any]:
    if not url or not str(url).startswith(("http://", "https://")):
        return {"url": url, "downloaded": False, "size": None, "sha256": None}
    try:
        timeout = aiohttp.ClientTimeout(total=45)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(str(url)) as resp:
                data = await resp.read()
                return {
                    "url": str(url),
                    "downloaded": resp.status == 200,
                    "http_status": resp.status,
                    "content_type": resp.headers.get("Content-Type"),
                    "size": len(data) if resp.status == 200 else None,
                    "sha256": _sha256_bytes(data) if resp.status == 200 else None,
                }
    except Exception as exc:
        return {"url": str(url), "downloaded": False, "size": None, "sha256": None, "hash_error": f"{type(exc).__name__}: {exc}"}


async def _traced_build_monologue(app: Any, context: Dict[str, Any], cfg: Dict[str, Any]) -> str:
    text = await _ORIGINAL_BUILD_MONOLOGUE(app, context, cfg)
    trace = _TRACE_CTX.get()
    if trace is not None:
        trace["voice_text"] = text
        trace["voice_text_len"] = len(str(text or ""))
        trace["voice_text_sha256"] = _sha256_text(text)
        _stage(app, trace, "voice_script_ready", {"text": text, "length": len(str(text or ""))}, snapshot=True)
    return text


async def _traced_tts(app: Any, script: str, cfg: Dict[str, Any]) -> str:
    trace = _TRACE_CTX.get()
    try:
        path = await _ORIGINAL_TTS(app, script, cfg)
        if trace is not None:
            info = _file_info(path)
            trace["sulafat_audio"] = info
            _stage(app, trace, "sulafat_tts_success", info, snapshot=True)
        return path
    except Exception as exc:
        if trace is not None:
            _stage(app, trace, "sulafat_tts_failure", {"exception": type(exc).__name__, "message": str(exc)}, snapshot=True)
        raise


async def _traced_subscribe(app: Any, model_id: str, arguments: Dict[str, Any], tag: str) -> Dict[str, Any]:
    trace = _TRACE_CTX.get()
    if trace is None:
        return await _ORIGINAL_SUBSCRIBE(app, model_id, arguments, tag)

    trace["attempt_count"] = int(trace.get("attempt_count") or 0) + 1
    attempt_no = trace["attempt_count"]
    args = _safe(dict(arguments or {}))
    prompt = str(arguments.get("prompt") or "")
    image_url = str(arguments.get("image_url") or "") or None
    ref_audio_urls = list(arguments.get("reference_audio_urls") or [])

    image_fingerprint = await _remote_hash(image_url)
    audio_fingerprints = []
    for u in ref_audio_urls[:3]:
        audio_fingerprints.append(await _remote_hash(str(u)))

    attempt = {
        "attempt": attempt_no,
        "tag": tag,
        "model_id": model_id,
        "arguments": args,
        "prompt_len": len(prompt),
        "prompt_sha256": _sha256_text(prompt),
        "image_fingerprint": image_fingerprint,
        "reference_audio_fingerprints": audio_fingerprints,
        "status": "submitted",
        "started_at": _now(),
    }
    trace.setdefault("fal_attempts", []).append(attempt)
    _stage(app, trace, "fal_request", attempt, snapshot=True)

    try:
        result = await _ORIGINAL_SUBSCRIBE(app, model_id, arguments, tag)
        attempt["status"] = "success"
        attempt["finished_at"] = _now()
        video = result.get("video") if isinstance(result, dict) else None
        attempt["video_url"] = video.get("url") if isinstance(video, dict) else None
        _stage(app, trace, "fal_success", {"attempt": attempt_no, "video_url": attempt.get("video_url")}, snapshot=True)
        return result
    except Exception as exc:
        info = diagnostics.extract_h3_error(exc)
        attempt["status"] = "failed"
        attempt["finished_at"] = _now()
        attempt["error"] = _safe(info)
        trace["last_error"] = _safe(info)
        trace["result"] = "failed"
        try:
            setattr(exc, "h3_trace_id", trace.get("trace_id"))
        except Exception:
            pass
        _stage(app, trace, "fal_failure", {"attempt": attempt_no, "error": info}, snapshot=True)
        _write_failed(app, trace)
        raise


async def _traced_generate(app: Any, context: Dict[str, Any]) -> Dict[str, Any]:
    trace = _new_trace(app, context)
    token = _TRACE_CTX.set(trace)
    context["h3_trace_id"] = trace["trace_id"]
    _stage(app, trace, "start", {"context_keys": sorted(str(k) for k in context.keys())}, snapshot=True)
    try:
        result = await _ORIGINAL_GENERATE(app, context)
        trace["result"] = "success"
        trace["voice_mode_final"] = result.get("voice_mode") if isinstance(result, dict) else None
        trace["output_video_url"] = result.get("video_url") if isinstance(result, dict) else None
        trace["output_local_url"] = result.get("local_url") if isinstance(result, dict) else None
        trace["output_local_path"] = result.get("local_path") if isinstance(result, dict) else None
        if isinstance(result, dict) and result.get("local_path"):
            trace["output_file"] = _file_info(str(result.get("local_path")))
        _stage(app, trace, "complete", {"voice_mode_final": trace.get("voice_mode_final"), "output_video_url": trace.get("output_video_url")}, snapshot=True)
        result["h3_trace_id"] = trace["trace_id"]
        return result
    except Exception as exc:
        trace["result"] = "failed"
        trace["last_error"] = _safe(diagnostics.extract_h3_error(exc))
        try:
            setattr(exc, "h3_trace_id", trace.get("trace_id"))
        except Exception:
            pass
        _stage(app, trace, "failed_final", {"error": trace.get("last_error")}, snapshot=True)
        _write_failed(app, trace)
        raise
    finally:
        _TRACE_CTX.reset(token)


def _format_error_with_trace(exc: Exception, cfg: Optional[Dict[str, Any]] = None) -> str:
    text = _ORIGINAL_FORMAT_ERROR(exc, cfg)
    trace_id = getattr(exc, "h3_trace_id", None)
    if trace_id:
        text += f"\n`trace_id: {trace_id}`"
    return text


def install_h3_trace(app: Any) -> Dict[str, Any]:
    if getattr(voiceover_mode, "_xiaoxia_h3_trace_installed", False):
        return {"patched": False, "reason": "already_installed"}

    # Patch the live v1.12.06h voiceover pipeline itself, not the old monolith.
    voiceover_mode._build_inner_monologue = _traced_build_monologue
    voiceover_mode._tts_sulafat_voiceover = _traced_tts
    voiceover_mode._subscribe = _traced_subscribe
    voiceover_mode.generate_voiceover_video = _traced_generate

    # v1.12.06h had already rebound these aliases during install_voiceover_mode().
    h3.generate_h3_video = _traced_generate
    app.generate_h3_video_from_context = lambda context: _traced_generate(app, context)

    # Structured Discord errors now expose a trace_id that maps to failed/<trace_id>.json.
    diagnostics.format_h3_error = _format_error_with_trace

    paths = _paths(app)
    voiceover_mode._xiaoxia_h3_trace_installed = True
    print(f"🧾 [H3_TRACE_ACTIVE] jsonl={paths['jsonl']} failed_dir={paths['failed']}")
    return {
        "patched": True,
        "jsonl": paths["jsonl"],
        "latest": paths["latest"],
        "failed_dir": paths["failed"],
        "image_sha256": True,
        "prompt_sha256": True,
        "voice_sha256": True,
        "structured_error": True,
    }
