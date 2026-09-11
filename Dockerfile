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

# v1.12.06ap：/衣櫃 穿 Wxxx 可選附一張 Pose Reference。
# 測試路徑：Figure 1-8 = 小俠 Identity；Figure 9 = 原姿勢圖；Figure 10 = Wxxx 衣服；Seedream V4.5。
# 沒附圖時完全維持原 /衣櫃 穿 行為；Pose 為 one-shot，只作用下一張 /photo。
CMD npx openclaw gateway start & python xiaoxia_runtime_v11206ap.py
