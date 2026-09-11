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

# v1.12.06az：Pose Reference 由 Gemini 同時判讀鏡位、可見身體範圍與可見姿勢；
# Figure 9 只約束畫面中真正看得到的身體區域，close-up 不再被迫補全下半身或為了 Wxxx 拉遠。
# generic /photo、/photo 拍照、/photo 拍一張等從原始 context 判定，避免 downstream message 誤判。
# 保留 ay Pose Authority、ax 鏡位可視診斷、au Director TypeError 修正、at legacy 附件流程與 H3 修正。
CMD npx openclaw gateway start & python xiaoxia_runtime_v11206az.py
