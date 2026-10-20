# syntax=docker/dockerfile:1
# API image. Build from the repository root (the knowledge base in data/ is baked in):
#   docker build -f backend/Dockerfile -t car-support-api .

FROM python:3.12.15-slim-bookworm AS build
COPY --from=ghcr.io/astral-sh/uv:0.13.1 /uv /bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
WORKDIR /app
# Dependencies first: this layer is reused until uv.lock changes.
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --no-install-project
COPY backend/ ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev

FROM python:3.12.15-slim-bookworm
# uid 1000: also what Hugging Face Spaces runs containers as.
RUN useradd --create-home --uid 1000 app
WORKDIR /app
COPY --from=build --chown=app /app /app
COPY --chown=app data /app/data
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    CS_DATA_DIR=/app/data \
    CS_API_HOST=0.0.0.0
USER app
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz')"
# Apply migrations, then serve. Index the knowledge base once with: car-support ingest
CMD ["sh", "-c", "alembic upgrade head && exec car-support serve"]
