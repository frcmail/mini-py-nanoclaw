FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1
ENV NANOCLAW_HOME=/data/nanoclaw

WORKDIR /app

COPY pyproject.toml README.md /app/
COPY nanoclaw /app/nanoclaw

RUN python -m pip install --upgrade pip \
    && python -m pip install --no-cache-dir /app

RUN mkdir -p /data/nanoclaw/groups /data/nanoclaw/store /data/nanoclaw/data

RUN groupadd -r nanoclaw && useradd -r -g nanoclaw nanoclaw \
    && chown -R nanoclaw:nanoclaw /data/nanoclaw
USER nanoclaw

VOLUME ["/data/nanoclaw"]

CMD ["python", "-m", "nanoclaw"]
