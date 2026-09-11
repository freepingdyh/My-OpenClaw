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

# v1.12.06an：姿勢候選圖先審核，確認後才收入姿勢庫。
# 支援 Seedream v4.5 重抽與 Seedream v5 Pro 修姿勢；保留 9 張小俠 Identity refs。
# 保留 al Love Intent 顯示邊界、ai H3 native voice、ag prompt recovery、ae fal-native image transport。
CMD npx openclaw gateway start & python xiaoxia_runtime_v11206an.py
