# -*- coding: utf-8 -*-
"""Private external-API health checks for Xiaoxia.

These checks are intentionally non-destructive:
- OpenAI: one tiny text completion.
- SunoApi.org: credit-balance GET only; no song generation and no credits consumed.
No secret value is ever echoed back to Discord.
"""
from __future__ import annotations

import os
from typing import Any, Dict

import aiohttp


async def check_openai(app: Any) -> Dict[str, Any]:
    key_present = bool(str(os.environ.get("OPENAI_API_KEY") or "").strip())
    if not key_present:
        return {"ok": False, "service": "OpenAI", "detail": "OPENAI_API_KEY 未設定"}
    try:
        response = await app.openai_client.chat.completions.create(
            model="gpt-5-mini",
            messages=[{"role": "user", "content": "Reply with exactly: OPENAI_OK"}],
            max_completion_tokens=100,
        )
        content = str(response.choices[0].message.content or "").strip()
        return {
            "ok": content == "OPENAI_OK",
            "service": "OpenAI",
            "detail": content or "request succeeded but content was empty",
            "model": str(getattr(response, "model", "gpt-5-mini") or "gpt-5-mini"),
        }
    except Exception as exc:
        return {
            "ok": False,
            "service": "OpenAI",
            "detail": f"{type(exc).__name__}: {str(exc)[:500]}",
        }


async def check_suno() -> Dict[str, Any]:
    api_key = str(os.environ.get("SUNO_API_KEY") or "").strip()
    if not api_key:
        return {"ok": False, "service": "Suno", "detail": "SUNO_API_KEY 未設定"}
    url = "https://api.sunoapi.org/api/v1/generate/credit"
    headers = {"Authorization": f"Bearer {api_key}"}
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as resp:
                try:
                    payload = await resp.json(content_type=None)
                except Exception:
                    payload = {"raw": (await resp.text())[:500]}
        api_code = payload.get("code") if isinstance(payload, dict) else None
        data = payload.get("data") if isinstance(payload, dict) else None
        ok = resp.status == 200 and (api_code in (None, 200))
        credit = data
        if isinstance(data, dict):
            credit = data.get("credit") or data.get("credits") or data.get("balance") or data
        return {
            "ok": ok,
            "service": "Suno",
            "detail": "authentication accepted" if ok else str(payload)[:500],
            "http_status": resp.status,
            "api_code": api_code,
            "credits": credit,
        }
    except Exception as exc:
        return {
            "ok": False,
            "service": "Suno",
            "detail": f"{type(exc).__name__}: {str(exc)[:500]}",
        }


def _format_result(result: Dict[str, Any]) -> str:
    mark = "✅" if result.get("ok") else "❌"
    service = result.get("service") or "API"
    lines = [f"{mark} **{service}**"]
    if result.get("model"):
        lines.append(f"Model: `{result['model']}`")
    if result.get("http_status") is not None:
        lines.append(f"HTTP: `{result['http_status']}`")
    if result.get("api_code") is not None:
        lines.append(f"API code: `{result['api_code']}`")
    if result.get("credits") is not None:
        lines.append(f"Credits: `{result['credits']}`")
    lines.append(f"Result: `{str(result.get('detail') or '')[:700]}`")
    return "\n".join(lines)


def register_health_commands(app: Any) -> None:
    """Register private !test_openai / !test_suno / !test_api commands once."""
    bot = app.architect_bot

    for name in ("test_openai", "test_suno", "test_api"):
        existing = bot.get_command(name)
        if existing is not None:
            bot.remove_command(name)

    @bot.command(name="test_openai")
    async def _test_openai(ctx):
        if not app.private_command_authorized(ctx):
            await ctx.send("🔒 `!test_openai` 僅限管理者在私人工作室使用。")
            return
        await ctx.send("🧪 正在測 OpenAI（不顯示 API Key）……")
        await ctx.send(_format_result(await check_openai(app)))

    @bot.command(name="test_suno")
    async def _test_suno(ctx):
        if not app.private_command_authorized(ctx):
            await ctx.send("🔒 `!test_suno` 僅限管理者在私人工作室使用。")
            return
        await ctx.send("🧪 正在測 Suno API 認證與剩餘 credits；不會生成歌曲、不扣生成 credits……")
        await ctx.send(_format_result(await check_suno()))

    @bot.command(name="test_api")
    async def _test_api(ctx):
        if not app.private_command_authorized(ctx):
            await ctx.send("🔒 `!test_api` 僅限管理者在私人工作室使用。")
            return
        await ctx.send("🧪 正在做 OpenAI + Suno health check……")
        openai_result = await check_openai(app)
        suno_result = await check_suno()
        await ctx.send(_format_result(openai_result) + "\n\n" + _format_result(suno_result))

    print("🧪 [API_HEALTH_COMMANDS_REGISTERED] !test_openai !test_suno !test_api")
