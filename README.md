# Car Support Assistant

A production-grade customer-support assistant for a (fictional) car maker, Northwind Motors. It answers questions from the company's documents with citations, checks vehicle recalls and finds EV chargers through live open data, hands conversations to human agents, and is observable and evaluated in CI.

Everything runs on free, open-source software. Running it locally needs no account, API key or payment.

| | |
|---|---|
| **Answers** | Grounded in 55 documents (DE, UK, US markets; English and German; Markdown, HTML, PDF) plus GOV.UK guidance; every fact cited and checkable |
| **Quality** | On 184 golden questions, the local `gemma3:4b` pipeline takes the right path 95% of the time and answers 86% fully correctly; retrieval puts a relevant passage in the top 4 for 97% |
| **Safety** | Personal data removed before any model, log or trace sees it; prompt-injection attempts refused before any model call; answers without valid citations are not shown |
| **Operations** | Streaming API, agent desk with handoff tickets, Prometheus/Grafana dashboard, Phoenix traces, CI with retrieval gate, security scans and a nightly LLM-judged evaluation |

## Run it

Requirements: [Docker Desktop](https://www.docker.com/products/docker-desktop/) (or Podman) and [Ollama](https://ollama.com) with `ollama pull qwen3-embedding:4b` and `ollama pull gemma3:4b`. The full local stack wants about 16 GB RAM; see [ADR 0004](docs/adr/0004-pipeline-and-models.md) for lighter options.

```bash
cp backend/.env.example backend/.env          # optional keys (Groq, Open Charge Map), agent secret
cp frontend/.env.example frontend/.env.local  # agent sign-in settings
docker compose --profile app up -d --build    # Postgres, API (:8000) and web app (:3000)
docker compose run --rm api car-support ingest   # index the knowledge base once (incremental later)
```

Open http://127.0.0.1:3000 for the chat and http://127.0.0.1:3000/agent for the agent desk. Add `--profile observability` for Phoenix (:6006), Prometheus (:9090) and Grafana (:3001).

### Public demo (free, no account)

```bash
cloudflared tunnel --url http://localhost:3000   # prints a https://...trycloudflare.com link
```

The link works while the command runs and changes each time; see [ADR 0007](docs/adr/0007-deployment.md) for why there is no always-on free host.

### Develop

```bash
docker compose up -d                       # Postgres only
cd backend && uv sync && uv run alembic upgrade head && uv run car-support ingest
uv run car-support serve                   # add --reload while editing
cd ../frontend && npm install && npm run dev
```

Tests and evaluation (from `backend/` unless noted):

```bash
uv run pytest                                                   # 250+ unit and integration tests (Docker needed)
uv run python eval/run.py retrieval                             # retrieval metrics -> eval/results/
uv run python eval/run.py answers --judge groq:qwen/qwen3.8-27b # full pipeline + LLM judge (needs a free Groq key)
cd ../frontend && npm run lint && npm run typecheck && npm run test:e2e
```

## How it works

```
Browser ── Next.js web app ── /backend/* ──► FastAPI ──► LangGraph pipeline
                     └── /api/agent/* (signed-in agents) ──┘     guard → understand → cache → retrieve → generate → validate
                                                                   └► recall (NHTSA) · chargers (Open Charge Map) · handoff
FastAPI ──► Postgres + pgvector (documents, chunks, conversations, tickets, feedback, cache)
        ──► Ollama (qwen3-embedding:4b, gemma3:4b) or Groq's free tier
        ──► /metrics (Prometheus → Grafana) · OpenTelemetry traces (Phoenix)
```

Details: [architecture](docs/architecture.md), [runbook](docs/runbook.md), [data](data/README.md), [frontend](frontend/README.md).

## Decisions

Every choice was measured on the golden set; each record gives the numbers.

| ADR | Decision |
|---|---|
| [0001](docs/adr/0001-postgres-pgvector-single-store.md) | One Postgres + pgvector store for vectors, keywords, filters and app data |
| [0002](docs/adr/0002-ingestion-pipeline.md) | Convert every format to Markdown, chunk by heading, index incrementally by content hash |
| [0003](docs/adr/0003-retrieval.md) | Dense search with `qwen3-embedding:4b` (Hit@1 87%, Hit@4 97%), no reranker (measured: no gain), per-model off-topic gate |
| [0004](docs/adr/0004-pipeline-and-models.md) | One structured "understand" call plus deterministic guards; local model by default, free cloud tier optional |
| [0005](docs/adr/0005-guardrails.md) | Rules first, model-based checks on top; no personal data reaches models; output validation |
| [0006](docs/adr/0006-observability.md) | Prometheus metrics, Grafana dashboard, Phoenix traces without personal data |
| [0007](docs/adr/0007-deployment.md) | Containers, one public origin, Cloudflare quick tunnel for the free demo |

## Repository

| Path | Contents |
|---|---|
| `backend/` | Python package `car_support`: ingestion, retrieval, pipeline, API, guardrails, observability, CLI; migrations; tests; `eval/` with the golden set, runner and judge |
| `frontend/` | Next.js customer chat and agent desk |
| `data/` | Knowledge base and its catalog |
| `infra/` | Prometheus config and the Grafana dashboard |
| `.github/workflows/` | CI (lint, types, tests, Playwright, retrieval gate, security) and the nightly evaluation |
| `docs/` | Plan, architecture, runbook, decision records |

## License

MIT. The knowledge base is fictional, except the GOV.UK pages (Open Government Licence v3.0); live data from NHTSA (public domain), OpenStreetMap (ODbL) and Open Charge Map (CC BY 4.0) is attributed where shown.
