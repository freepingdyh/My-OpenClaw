# 小俠女友聊天引擎切換

只切換 My-OpenClaw 的女友主要聊天模型。原有的完整 prompt、對話紀錄、人物設定、圖片輸入與後續 Discord 處理保留；TTS、圖片/影片生成、月曆、記憶與承諾等背景分析仍使用既有設定。小俠說故事機器人不受影響。

Zeabur 環境變數（修改後重新啟動服務）：

| Variable | Value / default |
|---|---|
| XIAOXIA_CHAT_PROVIDER | gemini (default), openai |
| XIAOXIA_GEMINI_MODEL | existing value unchanged |
| XIAOXIA_OPENAI_MODEL | gpt-6-luna |
| XIAOXIA_OPENAI_REASONING_EFFORT | defaults to none for gpt-6-luna; other models omit unless explicitly set; blank omits |
| XIAOXIA_OPENAI_MAX_OUTPUT_TOKENS | 4096 |
| OPENAI_API_KEY | existing secret; never commit to Git |

Only the chosen provider receives the primary chat request. There is no automatic cross-provider retry. OpenAI uses Responses API with store=False and the existing conversation context supplied each turn. Some auxiliary Gemini calls may still occur.

Check startup logs for [XIAOXIA_CHAT_PROVIDER] and chat logs for [GIRLFRIEND_REPLY_PATH] OPENAI_OK. Switch back by setting XIAOXIA_CHAT_PROVIDER=gemini and restarting.

Mock test: python -m unittest discover -s . -p test_chat_provider.py
Live API/deployment verification is separate.
