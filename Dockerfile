FROM ghcr.io/openclaw/openclaw:2026.3.8
COPY --chown=node:node ./skills /tmp/initial_skills/
CMD cp -r -n /tmp/initial_skills/* /home/node/.openclaw/workspace/skills/ && /bin/sh -c "/opt/openclaw/startup.sh && /opt/openclaw/start_gateway.sh"