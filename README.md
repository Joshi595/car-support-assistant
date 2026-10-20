# Car Support Assistant

A production-grade customer-support assistant for a (fictional) car maker. It answers questions from the company's documents with citations, uses live open-data tools (vehicle recalls, EV chargers), hands conversations to human agents, and is fully observable and evaluated in CI.

Everything runs on free, open-source software. Running locally needs no account, API key or payment.

> **Status:** Phase 8 (observability) complete: Prometheus metrics, Grafana dashboard and Phoenix traces ([ADR 0006](docs/adr/0006-observability.md), [runbook](docs/runbook.md)). On 184 golden questions the local gemma3:4b pipeline routes 95% correctly and answers 86% fully correctly with citations ([ADR 0004](docs/adr/0004-pipeline-and-models.md)). The roadmap is in [docs/plan.md](docs/plan.md).

## Quick start (development)

Requirements: [uv](https://docs.astral.sh/uv/), [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Podman), [Ollama](https://ollama.com) with `ollama pull qwen3-embedding:4b` and `ollama pull gemma3:4b`. The full local stack wants about 16 GB RAM; see [ADR 0004](docs/adr/0004-pipeline-and-models.md) for lighter options.

```bash
docker compose up -d                 # Postgres + pgvector (add --profile ollama if Ollama is not installed locally)
cd backend
cp .env.example .env                 # every value has a working local default
uv sync                              # install dependencies into backend/.venv
uv run alembic upgrade head          # create the database schema
uv run car-support ingest            # index data/ (incremental; --full to rebuild)
uv run car-support serve             # API on http://127.0.0.1:8000, docs at /docs
```

Ask a question (the answer streams as Server-Sent Events):

```bash
curl -N http://127.0.0.1:8000/v1/chat -H "Content-Type: application/json" \
     -d '{"market": "uk", "message": "How long is the battery warranty?"}'
```

Tests and evaluation:

```bash
uv run pytest                                 # unit + integration tests (integration tests need Docker)
uv run python eval/run.py retrieval           # retrieval metrics       -> eval/results/
uv run python eval/run.py answers             # full pipeline, 184 questions -> eval/results/
```

Code quality: `uv run ruff format . && uv run ruff check . && uv run mypy src tests alembic eval`. Install the git hooks once with `uv run pre-commit install`.

## API

| Route | Who | Purpose |
|---|---|---|
| `POST /v1/chat` | customer | Ask a question. Streams `meta` (conversation id), `token` (draft text) and `done` (validated answer, outcome, sources, whether to offer a human). |
| `POST /v1/feedback` | customer | Thumbs up/down on an answer (`rating` 1 or -1, optional comment). |
| `POST /v1/handoff` | customer | Accept the offer to talk to a person; opens a ticket. |
| `GET /v1/conversations/{id}` | customer | The conversation so far (the random id is the customer's handle). |
| `GET /v1/admin/tickets`, `GET/PATCH /v1/admin/tickets/{id}` | agent | Handoff queue with full transcript and cited sources; take and resolve tickets. |
| `GET /v1/admin/feedback` | agent | Rated answers with their questions (`?rating=-1` for the bad ones). |
| `POST /v1/admin/reindex` | agent | Incremental re-index of `data/` in the background. |
| `GET /healthz`, `GET /readyz` | ops | Liveness; readiness (database and Ollama reachable). |

Agent routes need a signed token (HS256 JWT). Set `CS_AGENT_JWT_SECRET` in `.env`, then `uv run car-support agent-token you@example.com` prints one for development; in production the frontend's sign-in issues it. Personal data (emails, phone numbers, VINs, IBANs, card numbers) is redacted before any model sees a message and before it is stored; clear prompt-injection attempts are refused before any model call. Knowledge-base answers are cached per question, market, language, date, index version and model.

## Repository layout

| Path | Contents |
|---|---|
| `backend/` | Python package `car_support`: config, ingestion (`ingest/`), retrieval, pipeline (`pipeline/`), HTTP API (`api/`), guardrails, CLI; Alembic migrations; tests |
| `data/` | Knowledge base: fictional brand corpus (DE/UK/US, EN/DE, md/html/pdf) and open-licensed public guidance, see [data/README.md](data/README.md) |
| `backend/eval/` | 184 golden questions across 16 categories, the evaluation runner and its reports |
| `compose.yaml` | Local infrastructure |
| `.github/workflows/` | CI: format, lint, type check, unit + integration tests |
| `frontend/` | Next.js customer chat and agent desk, see [frontend/README.md](frontend/README.md) |
| `infra/` | Prometheus config and the provisioned Grafana dashboard |
| `docs/` | [Plan](docs/plan.md), [runbook](docs/runbook.md) and [architecture decision records](docs/adr/) |

## License

MIT
