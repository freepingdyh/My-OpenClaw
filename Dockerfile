# 使用較新的 Node.js 20 Debian Bookworm 映像檔作為基底
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

# v1.12.06n：所有小俠圖片模組共用同一個 Gemini H3 Director。
# Director 先從 authoritative_scene 決定一句 video_theme，再產生單一 Hero Action、Reaction、Camera Intent、旁白與環境音。
# 不使用模組專屬策略表，也不建立場景動作資料庫；H3 改為原生台灣年輕女聲「畫外旁白」，畫面中的小俠不對嘴。
# persistent trace 與 body.image_url / body.prompt 診斷重試機制繼續保留。
CMD npx openclaw gateway start & python xiaoxia_runtime_v11206n.py
