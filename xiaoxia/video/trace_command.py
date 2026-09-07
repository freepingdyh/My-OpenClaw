# -*- coding: utf-8 -*-
"""Discord command for reading persistent H3 trace records from /data/memory/h3_trace."""
from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional


def _paths(app: Any) -> Dict[str, str]:
    memory_dir = str(getattr(app, "MEMORY_DIR", "") or "/data/memory")
    base = os.path.join(memory_dir, "h3_trace")
    return {
        "base": base,
        "jsonl": os.path.join(base, "h3_trace.jsonl"),
        "latest": os.path.join(base, "latest.json"),
        "failed": os.path.join(base, "failed"),
    }


def _load_json(path: str) -> Optional[Dict[str, Any]]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _find_trace(app: Any, trace_id: str) -> Optional[Dict[str, Any]]:
    paths = _paths(app)
    tid = str(trace_id or "").strip()
    if not tid:
        return None

    failed_path = os.path.join(paths["failed"], f"{tid}.json")
    data = _load_json(failed_path)
    if data:
        return data

    # Search newest-first from jsonl when a success trace or non-failed stage is requested.
    try:
        with open(paths["jsonl"], "r", encoding="utf-8") as f:
            rows = f.readlines()
        for line in reversed(rows[-2000:]):
            try:
                obj = json.loads(line)
            except Exception:
                continue
            if isinstance(obj, dict) and str(obj.get("trace_id") or "") == tid:
                return obj
    except Exception:
        pass
    return None


def _latest_trace(app: Any) -> Optional[Dict[str, Any]]:
    data = _load_json(_paths(app)["latest"])
    if not data:
        return None
    last = data.get("last")
    return last if isinstance(last, dict) else None


def _short(value: Any, limit: int = 260) -> str:
    text = " ".join(str(value or "").split())
    return text if len(text) <= limit else text[:limit] + "…"


def _latest_attempt(trace: Dict[str, Any]) -> Dict[str, Any]:
    attempts = trace.get("fal_attempts")
    if isinstance(attempts, list) and attempts:
        item = attempts[-1]
        return item if isinstance(item, dict) else {}
    return {}


def _format_trace(trace: Dict[str, Any]) -> str:
    attempt = _latest_attempt(trace)
    err = trace.get("last_error") if isinstance(trace.get("last_error"), dict) else {}
    if not err and isinstance(attempt.get("error"), dict):
        err = attempt.get("error")

    image_fp = attempt.get("image_fingerprint") if isinstance(attempt.get("image_fingerprint"), dict) else {}
    local_fp = trace.get("source_image_local") if isinstance(trace.get("source_image_local"), dict) else {}

    lines = ["🧾 **H3 Trace**"]
    lines.append(f"`trace_id: {trace.get('trace_id')}`")
    lines.append(f"`result: {trace.get('result')}`")
    lines.append(f"`module: {trace.get('module')}`")
    lines.append(f"`attempt_count: {trace.get('attempt_count')}`")
    lines.append(f"`voice_mode: {trace.get('voice_mode')}`")
    lines.append(f"`duration: {trace.get('duration_sec')}s | resolution: {trace.get('resolution')}`")
    lines.append(f"`safety_checker: {str(bool(trace.get('safety_checker'))).lower()}`")
    if attempt:
        lines.append(f"`model: {attempt.get('model_id')}`")
        lines.append(f"`prompt_len: {attempt.get('prompt_len')}`")
        if attempt.get("prompt_sha256"):
            lines.append(f"`prompt_sha256: {attempt.get('prompt_sha256')}`")
    if image_fp:
        lines.append(f"`image_url_http: {image_fp.get('http_status')}`")
        lines.append(f"`image_url_size: {image_fp.get('size')}`")
        if image_fp.get("sha256"):
            lines.append(f"`image_url_sha256: {image_fp.get('sha256')}`")
    if local_fp and local_fp.get("sha256"):
        lines.append(f"`local_image_sha256: {local_fp.get('sha256')}`")
    if trace.get("voice_text"):
        lines.append(f"`voice_text: {_short(trace.get('voice_text'), 180)}`")
    if err:
        if err.get("http_status") is not None:
            lines.append(f"`http: {err.get('http_status')}`")
        if err.get("type"):
            lines.append(f"`type: {err.get('type')}`")
        if err.get("loc"):
            lines.append(f"`loc: {err.get('loc')}`")
        if err.get("msg"):
            lines.append(f"`msg: {_short(err.get('msg'), 220)}`")

    return "\n".join(lines)


def install_h3_trace_command(app: Any) -> Dict[str, Any]:
    bot = getattr(app, "girlfriend_bot", None)
    if bot is None:
        raise RuntimeError("girlfriend_bot not found")

    bot.remove_command("H3紀錄")
    bot.remove_command("h3trace")

    @bot.command(name="H3紀錄", aliases=["h3trace"])
    async def h3_trace_command(ctx, *, arg: str = "最近"):
        token = str(arg or "").strip()
        if token.lower() in {"最近", "latest", "last"}:
            trace = _latest_trace(app)
        else:
            trace = _find_trace(app, token)
        if not trace:
            await ctx.reply("找不到這筆 H3 trace。可用 `/H3紀錄 最近`，或貼完整 trace_id。", mention_author=False)
            return
        await ctx.reply(_format_trace(trace), mention_author=False)

    app.h3_trace_find = lambda trace_id: _find_trace(app, trace_id)
    app.h3_trace_latest = lambda: _latest_trace(app)
    return {
        "patched": True,
        "command": "/H3紀錄 <trace_id|最近>",
        "jsonl": _paths(app)["jsonl"],
    }
