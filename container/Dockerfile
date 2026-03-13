# NanoClaw Python Agent Container
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    chromium \
    fonts-liberation \
    fonts-noto-cjk \
    fonts-noto-color-emoji \
    libgbm1 \
    libnss3 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    libx11-xcb1 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libasound2 \
    libpangocairo-1.0-0 \
    libcups2 \
    libdrm2 \
    libxshmfence1 \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

ENV AGENT_BROWSER_EXECUTABLE_PATH=/usr/bin/chromium
ENV PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH=/usr/bin/chromium

WORKDIR /app
COPY pyproject.toml /app/pyproject.toml
COPY nanoclaw /app/nanoclaw

RUN pip install --no-cache-dir croniter==2.0.7

RUN mkdir -p /workspace/group /workspace/global /workspace/extra /workspace/ipc/messages /workspace/ipc/tasks /workspace/ipc/input

RUN printf '#!/bin/bash\nset -e\ncat > /tmp/input.json\npython -m nanoclaw.agent_runner < /tmp/input.json\n' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

WORKDIR /workspace/group
ENTRYPOINT ["/app/entrypoint.sh"]
