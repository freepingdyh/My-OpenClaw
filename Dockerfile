# 使用較新的 Node.js 20 Debian Bookworm映像檔作為基底
# bullseye-security 套件索引已出現 404，改用 bookworm 避免舊版安全倉庫套件版本失效。
FROM node:20-bookworm-slim

# 安裝 Python 3、venv、pip、ffmpeg 與必要編譯工具
RUN apt-get update && \
    apt-get install -y --no-install-recommends python3 python3-pip python3-venv build-essential ffmpeg && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 設定工作目錄
WORKDIR /workspace

# Bookworm 受 PEP 668 保護，不直接污染 system Python；統一使用專案虛擬環境。
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# 優先複製 requirements.txt 以利用 Docker 快取機制
COPY requirements.txt .

# 安裝 Python 依賴套件到 venv
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements.txt

# 複製專案內的所有檔案到容器的工作目錄
COPY . .

# 全域安裝 openclaw 框架
RUN npm install -g openclaw

# v1.12.06af：延續 ae 的 fal-native source-image transport 與 ad/ac 的 Gemini Director。
# H3 request 只含 Action / Reaction / Camera / natural ambience，不再送 Gemini/Sulafat 旁白文字或 speech 指令。
# H3 成片後才另外用 Sulafat TTS + ffmpeg 混入畫外音；TTS/混音失敗時保留 H3 ambient-only 成片，
# 不以 H3 native narration 作 fallback，也不做 prompt sanitizing retry。
CMD npx openclaw gateway start & python xiaoxia_runtime_v11206af.py
