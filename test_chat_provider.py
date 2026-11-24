"""Isolated tests; no credentials, network, Discord or paid API calls."""
import os
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from xiaoxia.chat_provider import install_chat_provider


class ChatProviderTests(unittest.IsolatedAsyncioTestCase):
    def app(self):
        create = AsyncMock(return_value=SimpleNamespace(
            output_text="你好", status="completed"))
        original = AsyncMock(return_value=("原本回覆", "LONG_CONTEXT_OK"))
        return SimpleNamespace(
            _send_girlfriend_with_safe_retry=original,
            XIAOXIA_GEMINI_MODEL="gemini-test",
            openai_client=SimpleNamespace(responses=SimpleNamespace(create=create)),
        )

    async def test_default_leaves_gemini_untouched(self):
        app = self.app()
        original = app._send_girlfriend_with_safe_retry
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(install_chat_provider(app), "gemini")
        self.assertIs(app._send_girlfriend_with_safe_retry, original)
        app.openai_client.responses.create.assert_not_called()

    async def test_openai_uses_same_prompt_and_multimodal_input(self):
        app = self.app()
        original = app._send_girlfriend_with_safe_retry
        with patch.dict(os.environ, {"XIAOXIA_CHAT_PROVIDER": "openai"}, clear=True):
            self.assertEqual(install_chat_provider(app), "openai")
        parts = [SimpleNamespace(inline_data=SimpleNamespace(
            mime_type="image/png", data=b"image")),
            SimpleNamespace(text="今天好嗎？")]
        reply = await app._send_girlfriend_with_safe_retry(
            "u", parts, "今天好嗎？", "now", "original prompt and memory")
        self.assertEqual(reply, ("你好", "OPENAI_OK"))
        kwargs = app.openai_client.responses.create.await_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-6-luna")
        self.assertTrue(kwargs["instructions"].startswith("original prompt and memory\n\n"))
        self.assertIn("不必等大俠提醒", kwargs["instructions"])
        self.assertIn("[[STICKER:名稱]]", kwargs["instructions"])
        self.assertEqual(kwargs["reasoning"], {"effort": "none"})
        self.assertFalse(kwargs["store"])
        self.assertEqual(kwargs["input"][0]["content"][0]["image_url"],
                         "data:image/png;base64,aW1hZ2U=")
        self.assertEqual(kwargs["input"][0]["content"][1]["text"], "今天好嗎？")
        original.assert_not_awaited()

    async def test_custom_model_and_error_never_switch_provider(self):
        app = self.app()
        original = app._send_girlfriend_with_safe_retry
        app.openai_client.responses.create.side_effect = RuntimeError("test")
        with patch.dict(os.environ, {
            "XIAOXIA_CHAT_PROVIDER": "openai",
            "XIAOXIA_OPENAI_MODEL": "gpt-4o-mini",
            "XIAOXIA_OPENAI_MAX_OUTPUT_TOKENS": "800",
        }, clear=True):
            install_chat_provider(app)
        reply = await app._send_girlfriend_with_safe_retry(
            "u", [], "hello", "now", "prompt")
        self.assertEqual(reply[1], "OPENAI_FALLBACK")
        kwargs = app.openai_client.responses.create.await_args.kwargs
        self.assertEqual(kwargs["model"], "gpt-4o-mini")
        self.assertEqual(kwargs["max_output_tokens"], 800)
        self.assertNotIn("reasoning", kwargs)
        original.assert_not_awaited()

    async def test_incomplete_response_is_not_saved_as_success(self):
        app = self.app()
        app.openai_client.responses.create.return_value = SimpleNamespace(
            output_text="partial", status="incomplete")
        with patch.dict(os.environ, {"XIAOXIA_CHAT_PROVIDER": "openai"}, clear=True):
            install_chat_provider(app)
        result = await app._send_girlfriend_with_safe_retry(
            "u", [], "hello", "now", "prompt")
        self.assertEqual(result[1], "OPENAI_FALLBACK")

    def test_unknown_provider_is_rejected(self):
        with patch.dict(os.environ, {"XIAOXIA_CHAT_PROVIDER": "typo"}, clear=True):
            with self.assertRaises(ValueError):
                install_chat_provider(self.app())


if __name__ == "__main__":
    unittest.main()
