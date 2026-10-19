# Car Support Assistant

A production-grade customer-support assistant for a (fictional) car maker. It answers questions from the company's documents with citations, uses live open-data tools (vehicle recalls, EV chargers), hands conversations to human agents, and is fully observable and evaluated in CI.

Everything runs on free, open-source software. Running locally needs no account, API key or payment.

> **Status:** Phase 0 (foundations). The roadmap is in [docs/plan.md](docs/plan.md).

## Quick start (development)

Requirements: [uv](https://docs.astral.sh/uv/), [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Podman), [Ollama](https://ollama.com).

```bash
docker compose up -d                 # Postgres + pgvector (add --profile ollama if Ollama is not installed locally)
cd backend
cp .env.example .env                 # every value has a working local default
uv sync                              # install dependencies into backend/.venv
uv run alembic upgrade head          # create the database schema
uv run pytest                        # tests (integration tests need Docker)
```

Code quality: `uv run ruff format . && uv run ruff check . && uv run mypy src tests alembic`. Install the git hooks once with `uv run pre-commit install`.

## Repository layout

| Path | Contents |
|---|---|
| `backend/` | Python package `car_support` (config, logging, database), Alembic migrations, tests |
| `compose.yaml` | Local infrastructure |
| `.github/workflows/` | CI: format, lint, type check, unit + integration tests |
| `docs/` | Plan and, later, architecture, runbook and decision records |

## License

MIT
