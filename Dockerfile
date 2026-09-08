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

# v1.12.06z：保留 y 的私有影片 archive 與刪除能力；
# Discord 統一改用 provider-agnostic `/video_delete [日期]`：日期省略=今天（Asia/Taipei），
# 列出當日所有收藏影片的編號/時間/模型/主題/規格，選號後二次確認再刪除。
# 不綁 H3；未來 Seedance/Wan/Grok 等只要進同一 video archive，就可用同一指令管理。
CMD npx openclaw gateway start & python xiaoxia_runtime_v11206z.py
