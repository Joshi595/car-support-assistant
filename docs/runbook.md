# Runbook

How to operate the assistant: start it, watch it, fix the common problems. Commands run from `backend/` unless stated.

## Start and stop

```bash
docker compose up -d                                   # Postgres
docker compose --profile observability up -d           # + Phoenix (6006), Prometheus (9090), Grafana (3001)
uv run alembic upgrade head && uv run car-support ingest
CS_TRACING_ENDPOINT=http://127.0.0.1:6006/v1/traces uv run car-support serve
cd ../frontend && npm run dev                          # http://127.0.0.1:3000, agent desk at /agent
```

Everything in containers instead (from the repository root):

```bash
docker compose --profile app up -d --build && docker compose run --rm api car-support ingest
cloudflared tunnel --url http://localhost:3000     # optional public demo link, valid while it runs
```

## Watch

| Where | What to look at |
|---|---|
| Grafana, http://127.0.0.1:3001 | Replies, reply time p95, refusal and handoff rates, cache hits, ratings; slowest pipeline steps; failures |
| Phoenix, http://127.0.0.1:6006 | One trace per request: the rewritten question, route, retrieved passages with similarity, prompts, model output, time per step |
| API logs | JSON lines with `request_id` (also returned as the `X-Request-ID` header, so a customer report can be matched to its trace and log lines) |
| `GET /readyz` | 503 when Postgres or Ollama is unreachable |

Short time ranges just after an API restart undercount (a new counter's first value precedes the first scrape). Use 30 minutes or more.

## Common problems

| Symptom | Likely cause | Fix |
|---|---|---|
| Every reply is "service unavailable" | Chat model down or out of quota (`cs_model_errors_total` rising) | Check Ollama (`ollama ps`) or the Groq quota; set `CS_FALLBACK_CHAT_MODEL` to a chain, e.g. `groq:openai/gpt-oss-20b,ollama:gemma3:4b` |
| Answers take 10 s or more on a laptop | The embedding and chat models swap on a small GPU | Keep `CS_QUERY_EMBEDDING_ON_CPU=true`, or use `qwen3-embedding:0.6b` |
| "model runner has unexpectedly stopped" | Out of RAM | Close other applications; the full local stack wants about 16 GB |
| Charger questions say "unavailable" | No Open Charge Map key | Set `CS_OPEN_CHARGE_MAP_KEY` (free account) |
| Refusal rate jumps after a content change | Documents missing or re-indexing failed | `uv run car-support ingest`; then `uv run python eval/run.py retrieval` |
| Agent desk says "sign in as an agent" | Email not in `AGENT_EMAILS`, or session expired | Add the email in `frontend/.env.local`; sign in again |
| Agent desk says "AGENT_JWT_SECRET is not configured" | Frontend and backend secrets differ or are missing | `AGENT_JWT_SECRET` (frontend) must equal `CS_AGENT_JWT_SECRET` (backend) |

## Update the knowledge base

1. Add or edit files under `data/` (see `data/README.md`); add a `catalog.toml` entry for public, versioned or model-specific documents.
2. `uv run pytest tests/test_corpus.py` checks that the golden set still matches the documents.
3. `uv run car-support ingest` re-embeds only what changed and bumps the index version, which also invalidates the answer cache. Agents can trigger the same from the API (`POST /v1/admin/reindex`).
4. `uv run python eval/run.py retrieval` and `answers` before releasing.

## Rotate secrets

- `CS_AGENT_JWT_SECRET` / `AGENT_JWT_SECRET`: change both together; agent tokens last 5 minutes, so the switch is immediate.
- `NEXTAUTH_SECRET`: changing it signs every agent out.
- `CS_GROQ_API_KEY`, `CS_OPEN_CHARGE_MAP_KEY`: replace in `backend/.env` and restart the API.
