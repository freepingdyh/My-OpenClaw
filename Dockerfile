# 使用輕量級的 Node.js 20 映像檔作為基底
FROM node:20-bullseye-slim

# 安裝 Python 3, pip 以及必要的編譯工具
RUN apt-get update && \
    apt-get install -y python3 python3-pip python3-venv build-essential && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# 設定工作目錄
WORKDIR /workspace

# 優先複製 requirements.txt 以利用 Docker 快取機制
COPY requirements.txt .

# 安裝 Python 依賴套件 (為了避免污染系統環境，我們設定不使用快取)
# 移除 --break-system-packages 即可順利安裝
RUN pip3 install --no-cache-dir -r requirements.txt

# 複製專案內的所有檔案到容器的工作目錄
COPY . .

# 全域安裝 openclaw 框架
RUN npm install -g openclaw

# 啟動 OpenClaw Gateway 並在背景執行，隨後啟動小俠主程式
# & 符號能讓 OpenClaw 在背景跑，不會卡住後面的 python 執行
# 將原本的 openclaw 改成 npx openclaw
CMD npx openclaw gateway start & python3 lobster_discord.py