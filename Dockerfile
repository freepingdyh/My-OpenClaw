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

# v1.12.06bc：修正這張改為 3 refs：成品 A 為主要修正 authority + 2 張小俠 identity anchors。
# 不再讓 9 張 identity 與成品 A 競爭；repair prompt 只要求最小必要修正，其他照片內容以成品 A 為準。
# 其餘沿用 bb：/photo 附圖預設 Pose Reference，明確背景語意才走實景背景。
CMD npx openclaw gateway start & python xiaoxia_runtime_v11206bc.py
