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

# v1.12.06be：Pose 照片公開顯示/相簿資料不再混入 REFERENCE ROLE CONTRACT 與英文 Gemini debug。
# Pose 照片暫停舊 v5.0 場景升級：該流程會把 Figure 9 Pose Authority 換成 v5 背景板，導致姿勢與場景漂移。
# 仍保留 bd 的 Figure 9 Pose Geometry Authority、bc 的 3-ref 修正這張、bb 的 /photo 附件路由。
CMD npx openclaw gateway start & python xiaoxia_runtime_v11206be.py
