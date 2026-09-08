# 使用較新的 Node.js 20 Debian Bookworm映像檔作為基底
# bullseye-security 套件索引已出現 404，改用 bookworm 避免舊版安全倉庫套件版本失效。
FROM node:20-bookworm-slim

# 安裝 Python 3、venv、pip、ffmpeg 與必要編譯工具
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 python3-pip python3-venv build-essential ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /workspace
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt
COPY . .
RUN npm install -g openclaw

# v1.12.06ai：直接疊 ag，刻意 bypass ah 的 Gemini TTS/Leda 改動。
# H3 Max Turbo 自己生成 native audio；fal 的 Turbo schema 沒有 voice/speaker 欄位，
# 因此以 H3 prompt 指定年輕、明亮、自然的台灣女性畫外音風格。
# 保留 ag body.prompt recovery 與 ae fal-native image transport。
CMD npx openclaw gateway start & python xiaoxia_runtime_v11206ai.py
