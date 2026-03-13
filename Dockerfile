FROM ghcr.io/openclaw/openclaw:2026.3.8
# 搬到官方建議的正確路徑
COPY ./skills /home/node/.openclaw/workspace/skills/
# 確保權限正確，讓小俠能讀能寫
RUN chown -R node:node /home/node/.openclaw/workspace/skills/