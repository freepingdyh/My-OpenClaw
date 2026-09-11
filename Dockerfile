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

# v1.12.06bf：修正這張維持 3 refs（成品主圖 + 2 Identity anchors），但允許針對使用者指出的
# 手腳/關節/肢體長度等局部 anatomy 錯誤真正改動局部幾何；場景、服裝、鏡位、整體姿勢仍鎖定原成品。
# 同時保留 be 的 Pose 公開輸出清理與舊 v5 Pose guard，以及 bd/bb 的 Pose Authority/附件路由。
CMD npx openclaw gateway start & python xiaoxia_runtime_v11206bf.py
