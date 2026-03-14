FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV NANOCLAW_HOME=/data/nanoclaw

RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY nanoclaw /app/nanoclaw

RUN python -m pip install --upgrade pip \
    && python -m pip install /app

RUN mkdir -p /data/nanoclaw/groups /data/nanoclaw/store /data/nanoclaw/data

VOLUME ["/data/nanoclaw"]

CMD ["python", "-m", "nanoclaw"]
