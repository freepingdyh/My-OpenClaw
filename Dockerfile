FROM ghcr.io/openclaw/openclaw:2026.3.8
COPY --chown=node:node ./skills /home/node/.openclaw/workspace/skills/