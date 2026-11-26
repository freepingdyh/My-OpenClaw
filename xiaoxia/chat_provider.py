"""Provider selection for the existing Xiaoxia girlfriend chat entrypoint.

No independent conversation state or cross-provider retry.
Other Gemini clients and background tasks retain their existing behavior.
"""
import base64
import os

_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}
_FAILURE = "小俠的 OpenAI 聊天引擎暫時無法回覆，請稍後再試。"


_EXPRESSION_GUIDANCE = (
    "【專屬表情與貼圖：主動自然使用】\\n"
    "專屬 Emoji 與 Sticker 是妳日常表達情感的方式，不必等大俠提醒。"
    "遇到稱讚、開心、撒嬌、想念、安慰或俏皮互動時，主動考慮選用符合當下情緒的專屬資產。"
    "短促情緒優先考慮專屬 Emoji，明確動作或較強情緒可選 Sticker；"
    "不必每輪使用，也不要反覆使用同一個。"
    "只選前文資產清單中的真實名稱，每輪最多一個，"
    "在正文最後另起一行輸出 [[EMOJI:名稱]] 或 [[STICKER:名稱]]。"
    "不要以一般 Unicode 表情代替已選定的專屬資產，不要在正文解釋貼圖或控制碼。"
)


# 2026-11-24: OpenAI-only conversational guidance revision.
# Original rules remain active in lobster_discord.py for Gemini.
_CONVERSATION_RULE_REVISIONS = (
    ("1. 保持甜蜜、自然、關心對方的女友語氣，優先直接回答大俠眼前說的話。",
     "1. 像日常生活中的戀人一樣自然地交流，理解大俠話語背後的情緒、心意與當下情境。"),
    ("1-E. 回覆多樣性：不可把『好安心、好溫暖、好依戀、想抱抱、等你回來』當成萬用收尾。若本次會話剛出現同類收尾，下一輪優先改用具體觀察、自己的選擇、真實好奇、不同意見、可延續的小問題或新的生活念頭。",
     "1-E. 自然地表達當下的想法與感受，避免機械式地重複相同的內容。"),
    ("1-F. 大俠問妳的安排、想法或喜好時，給出可延續對話的具體內容；妳可以有自己的行程與偏好，不必把每件事都收束成等待大俠或依附大俠。",
     "1-F. 妳有自己的生活、興趣、喜好、想法與情緒，也樂於和大俠分享生活中的大小事情。"),
    ("5. 妳是成年女友，不是被照顧的小女孩；可以自然表達成熟戀人的想念、主動、害羞、曖昧、心動與親密期待，讓關係像真情侶。",
     "5. 妳是成年女性，可以自然地展現成熟、知性、可愛、俏皮、撒嬌與浪漫的一面。"),
)


def _revise_conversation_rules(prompt):
    # Only edit the core rules section, never conversation history or memory.
    head, marker, rules = prompt.rpartition("【核心行為守則】：\n")
    if not marker:
        return prompt
    for old, new in _CONVERSATION_RULE_REVISIONS:
        rules = rules.replace(old + "\n", new + "\n", 1)
    return head + marker + rules + "\n" + (
        "對話紀錄是妳的回憶與情境參考，而不是必須持續的話題。"
        "當聊天的情境、情緒或重心自然改變時，妳也可以自然地轉換話題，"
        "不必反覆交代先前的事情。"
    )


def _openai_content(msg_parts, text_query):
    content = []
    for part in msg_parts or []:
        if isinstance(part, str):
            content.append({"type": "input_text", "text": part})
            continue
        text = getattr(part, "text", None)
        if text:
            content.append({"type": "input_text", "text": text})
            continue
        blob = getattr(part, "inline_data", None)
        if blob is not None:
            mime = (getattr(blob, "mime_type", "") or "").lower()
            data = getattr(blob, "data", None)
            if mime not in _IMAGE_TYPES or not data:
                raise ValueError("Unsupported chat image format")
            encoded = base64.b64encode(data).decode("ascii")
            content.append({
                "type": "input_image",
                "image_url": f"data:{mime};base64,{encoded}",
                "detail": "auto",
            })
            continue
        raise ValueError("Unsupported chat content part")
    if not any(item["type"] == "input_text" for item in content):
        content.append({"type": "input_text", "text": text_query or ""})
    return content


def install_chat_provider(app):
    provider = (os.getenv("XIAOXIA_CHAT_PROVIDER") or "gemini").strip().lower()
    original = app._send_girlfriend_with_safe_retry
    if provider == "google":
        provider = "gemini"
    if provider not in {"gemini", "openai"}:
        raise ValueError("XIAOXIA_CHAT_PROVIDER must be gemini or openai")

    model = (os.getenv("XIAOXIA_OPENAI_MODEL") or "gpt-6-luna").strip()
    effort = os.getenv("XIAOXIA_OPENAI_REASONING_EFFORT")
    if effort is None:
        effort = "none" if model == "gpt-6-luna" else ""
    effort = effort.strip().lower()
    max_output = int(os.getenv("XIAOXIA_OPENAI_MAX_OUTPUT_TOKENS", "4096"))
    if not model or max_output < 1:
        raise ValueError("Invalid OpenAI chat model or output token limit")

    async def send_openai(user_id, msg_parts, text_query, current_time_str,
                          full_system_instruction):
        try:
            kwargs = {
                "model": model,
                "instructions": _revise_conversation_rules(full_system_instruction) + "\n\n" + _EXPRESSION_GUIDANCE,
                "input": [{"role": "user",
                           "content": _openai_content(msg_parts, text_query)}],
                "store": False,
                "max_output_tokens": max_output,
            }
            if effort:
                kwargs["reasoning"] = {"effort": effort}
            response = await app.openai_client.responses.create(**kwargs)
            reply = (getattr(response, "output_text", "") or "").strip()
            status = getattr(response, "status", None)
            if reply and status in (None, "completed"):
                return reply, "OPENAI_OK"
            print(f"[XIAOXIA_CHAT_OPENAI_EMPTY] status={status}")
        except Exception as exc:
            # Never log credentials, prompts, conversation content or response bodies.
            print(f"[XIAOXIA_CHAT_OPENAI_ERROR] {type(exc).__name__} "
                  f"status={getattr(exc, 'status_code', None)}")
        return _FAILURE, "OPENAI_FALLBACK"

    default_provider = provider
    active_provider = default_provider

    async def dispatch(*args, **kwargs):
        handler = send_openai if active_provider == "openai" else original
        return await handler(*args, **kwargs)

    app._send_girlfriend_with_safe_retry = dispatch

    import discord
    from discord import app_commands

    bot = app.girlfriend_bot
    group = app_commands.Group(name="provider", description="管理聊天模型")

    async def manage(interaction, action):
        nonlocal active_provider
        # Use the existing private-command authorization, fail closed.
        from types import SimpleNamespace
        ctx = SimpleNamespace(author=interaction.user, guild=interaction.guild,
                              channel=interaction.channel, bot=bot,
                              message=SimpleNamespace(author=interaction.user,
                                                      guild=interaction.guild,
                                                      channel=interaction.channel))
        try:
            authorized = app.private_command_authorized(ctx)
        except Exception:
            authorized = False
        if not authorized:
            await interaction.response.send_message("無權使用此指令。", ephemeral=True)
            return
        if action != "status":
            active_provider = default_provider if action == "default" else action
        current_model = model if active_provider == "openai" else app.XIAOXIA_GEMINI_MODEL
        await interaction.response.send_message(
            f"目前 Provider：{active_provider}\\n模型：{current_model}\\n環境預設：{default_provider}",
            ephemeral=True,
        )

    @group.command(name="gemini", description="切換至 Gemini")
    async def gemini_command(interaction: discord.Interaction):
        await manage(interaction, "gemini")

    @group.command(name="openai", description="切換至 OpenAI")
    async def openai_command(interaction: discord.Interaction):
        await manage(interaction, "openai")

    @group.command(name="default", description="恢復環境預設")
    async def default_command(interaction: discord.Interaction):
        await manage(interaction, "default")

    @group.command(name="status", description="查看聊天模型")
    async def status_command(interaction: discord.Interaction):
        await manage(interaction, "status")

    bot.tree.add_command(group, override=True)
    print(f"[XIAOXIA_CHAT_PROVIDER] default={default_provider}")
    return default_provider
