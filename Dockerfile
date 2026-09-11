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

# v1.12.06bd：/photo + Pose 改為 Figure 9 Pose Geometry Authority。
# Gemini visible-scope 只作觀察資訊，不再有權排除畫面中實際可見的骨盆、臀、腿或支撐幾何。
# Camera 只控制取景/視角；Figure 9 控制取景內的整體身體幾何。仍為 8 Identity + Pose + Wxxx → Seedream V4.5。
# 同時保留 bc 的「修正這張」3-ref patch 與 bb 的附件路由修正。
CMD npx openclaw gateway start & python xiaoxia_runtime_v11206bd.py
