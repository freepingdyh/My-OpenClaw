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

# v1.12.06as：native slash commands 立即 defer，並補齊 legacy ctx.reply / ctx.typing 相容層。
# 保留 ar 的 H3 TypeError 修正、aq 的 slash 註冊，以及 ap 的衣櫃+Pose 實驗。
CMD npx openclaw gateway start & python xiaoxia_runtime_v11206as.py
