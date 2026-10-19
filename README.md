# Car Support Assistant

A production-grade customer-support assistant for a (fictional) car maker. It answers questions from the company's documents with citations, uses live open-data tools (vehicle recalls, EV chargers), hands conversations to human agents, and is fully observable and evaluated in CI.

Everything runs on free, open-source software. Running locally needs no account, API key or payment.

> **Status:** Phase 2 (ingestion and storage) complete. The roadmap is in [docs/plan.md](docs/plan.md).

## Quick start (development)

Requirements: [uv](https://docs.astral.sh/uv/), [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Podman), [Ollama](https://ollama.com).

```bash
docker compose up -d                 # Postgres + pgvector (add --profile ollama if Ollama is not installed locally)
cd backend
cp .env.example .env                 # every value has a working local default
uv sync                              # install dependencies into backend/.venv
uv run alembic upgrade head          # create the database schema
uv run car-support ingest            # index data/ (incremental; --full to rebuild)
uv run pytest                        # tests (integration tests need Docker)
```

Code quality: `uv run ruff format . && uv run ruff check . && uv run mypy src tests alembic`. Install the git hooks once with `uv run pre-commit install`.

## Repository layout

| Path | Contents |
|---|---|
| `backend/` | Python package `car_support`: config, logging, database models, ingestion (`ingest/`), CLI; Alembic migrations; tests |
| `data/` | Knowledge base: fictional brand corpus (DE/UK/US, EN/DE, md/html/pdf) and open-licensed public guidance, see [data/README.md](data/README.md) |
| `backend/eval/golden.jsonl` | 184 evaluation questions across 16 categories, validated against the corpus by `tests/test_corpus.py` |
| `compose.yaml` | Local infrastructure |
| `.github/workflows/` | CI: format, lint, type check, unit + integration tests |
| `docs/` | [Plan](docs/plan.md) and [architecture decision records](docs/adr/) |

## License

MIT
