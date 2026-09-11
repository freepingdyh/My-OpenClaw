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

# v1.12.06ba：臨時 Pose Reference 改由 /photo 附圖輸入；衣櫃只維持穿著狀態。
# 生成仍沿用 az：8 Identity + Figure 9 Visible Pose + Figure 10 Wardrobe + Gemini Camera，單張消耗。
# 保留 ay Pose Authority、ax 鏡位可視診斷、au Director TypeError 修正、at legacy 附件流程與 H3 修正。
CMD npx openclaw gateway start & python xiaoxia_runtime_v11206ba.py
