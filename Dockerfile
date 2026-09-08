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

# v1.12.06ag：先救回昨天已驗證可用的 body.prompt 422 recovery。
# 正常路徑仍為 af：H3 只收視覺 Action/Reaction/Camera/ambience，Sulafat 僅成片後 post-mix；
# 若 fal 明確回 content_policy_violation/body.prompt，先以同一 Hero Action 的 action-only prompt 重試，
# 若仍為同一 422，再以 generic minimal-motion prompt 作最後 recovery。ae 的 fal-native image transport 保留。
CMD npx openclaw gateway start & python xiaoxia_runtime_v11206ag.py
