# syntax=docker/dockerfile:1
# Single-container, no-key portfolio demo for Hugging Face Docker Spaces.
# The full PostgreSQL/Redis deployment continues to use compose.yaml.
FROM node:22-bookworm-slim AS web-dependencies
WORKDIR /web
COPY frontend/package.json frontend/package-lock.json ./
RUN --mount=type=secret,id=build_ca,target=/tmp/build-ca.pem \
    if [ -f /tmp/build-ca.pem ]; then export NODE_EXTRA_CA_CERTS=/tmp/build-ca.pem; fi; \
    npm ci --no-audit --no-fund

FROM web-dependencies AS web-build
COPY frontend/ ./
ENV BACKEND_URL=http://127.0.0.1:8000 NEXT_TELEMETRY_DISABLED=1
RUN npm run build

FROM python:3.12-slim-bookworm AS runtime
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 \
    && rm -rf /var/lib/apt/lists/*
COPY --from=web-build /usr/local/bin/node /usr/local/bin/node
RUN --mount=type=secret,id=build_ca,target=/tmp/build-ca.pem \
    if [ -f /tmp/build-ca.pem ]; then export PIP_CERT=/tmp/build-ca.pem; fi; \
    pip install --no-cache-dir uv==0.12.23
WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=secret,id=build_ca,target=/tmp/build-ca.pem \
    if [ -f /tmp/build-ca.pem ]; then export SSL_CERT_FILE=/tmp/build-ca.pem; fi; \
    uv sync --frozen --no-dev
COPY backend/app ./app
COPY backend/migrations ./migrations
COPY backend/alembic.ini ./
COPY --from=web-build /web/.next/standalone /app/web/
COPY --from=web-build /web/.next/static /app/web/.next/static/
COPY deploy/space/start.py /app/start.py
RUN useradd --create-home --uid 1000 demo && mkdir -p /app/data \
    && chown -R demo:demo /app
USER demo
ENV PATH="/app/backend/.venv/bin:$PATH" HOME=/home/demo \
    PYTHONUNBUFFERED=1 NEXT_TELEMETRY_DISABLED=1 NODE_ENV=production
EXPOSE 7860
HEALTHCHECK --interval=30s --timeout=5s --start-period=45s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:7860/api/health', timeout=3)"
CMD ["python", "/app/start.py"]
