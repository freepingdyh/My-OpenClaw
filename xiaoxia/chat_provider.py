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
    if provider in {"gemini", "google"}:
        print(f"[XIAOXIA_CHAT_PROVIDER] gemini model={app.XIAOXIA_GEMINI_MODEL}")
        return "gemini"
    if provider != "openai":
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
                "instructions": full_system_instruction + "\n\n" + _EXPRESSION_GUIDANCE,
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

    # Original handler is unchanged and remains the default on the next restart.
    app._send_girlfriend_with_safe_retry = send_openai
    print(f"[XIAOXIA_CHAT_PROVIDER] openai model={model} reasoning={effort or 'default'}")
    return "openai"
