# Architecture

## Request path

1. **Browser → web app.** The customer chat (`/`) and the agent desk (`/agent`) are a Next.js app. The browser talks only to it: customer calls go to `/backend/v1/...` and agent calls to `/api/agent/...`. One origin means no CORS and one address to publish.
2. **Web app → API.** `/backend` forwards only the customer routes (chat, feedback, handoff, conversations) and passes on the client address for rate limiting. `/api/agent` checks the agent's sign-in (next-auth) and calls `/v1/admin/...` with a token valid for 5 minutes, signed with a secret the browser never sees.
3. **API → pipeline.** `POST /v1/chat` stores the redacted message, runs the LangGraph pipeline and streams Server-Sent Events: `meta`, then `token` drafts, then `done` with the validated answer, its sources and whether to offer a person.

## Pipeline (`backend/src/car_support/pipeline/graph.py`)

| Step | What it does | Model? |
|---|---|---|
| `guard` | Refuses clear prompt-injection attempts (English/German rules, optional Prompt Guard) | optional classifier |
| `understand` | One structured call: intent, standalone question (follow-ups resolved), tool arguments; then code checks the language, VINs and tool arguments | chat model |
| `cache` | Exact-match answer cache keyed by question, market, language, date, index version and model | no |
| `retrieve` | Embeds the question; dense search in the customer's market and the document versions valid today; off-topic gate | embedding model |
| `generate` | Answers only from the numbered passages, in the customer's language, citing `[n]` | chat model |
| `validate` | Normalises and checks citations, drops uncited answers and prompt leaks, removes echoed customer data | no |
| `recall` / `chargers` | NHTSA vPIC + Recalls; OpenStreetMap Nominatim + Open Charge Map | no |
| `handoff` / `refuse` / `off_topic` | Fixed replies in the customer's language; handoff opens a ticket | no |

Every model call retries once and then tries the fallback chain. If everything fails, the customer gets "service unavailable, shall I connect you with a colleague?" and never an error.

## Data

- **Knowledge base:** files in `data/` with `catalog.toml`. `car-support ingest` converts each one to Markdown, chunks it by heading, hashes the chunks and embeds only new or changed ones (ADR 0002).
- **Postgres:** `documents`, `chunks` (HNSW vector index and a language-aware full-text index), `kb_versions`, `conversations`, `messages` (redacted), `feedback`, `tickets` and `answer_cache`. Migrations are managed with Alembic.

## Observability

- **Metrics:** `/metrics` exposes replies by outcome, latency per step, cache, ratings, handoffs and failures; Grafana shows them (`infra/grafana`).
- **Traces:** one OpenTelemetry trace per request, sent to Phoenix, covering every step, prompt and retrieval. Personal data is removed before the pipeline starts.
- **Logs:** JSON lines carrying the request ID, which is also returned in `X-Request-ID`.

## Quality loop

- **Golden set:** 184 questions in 16 categories (`backend/eval/golden.jsonl`), checked against the documents by `tests/test_corpus.py`.
- **CI on every change:** lint, types, more than 250 tests, Playwright, a retrieval gate (real corpus, real embeddings), and security scans.
- **Nightly:** the full pipeline on Groq's free tier, graded by an LLM judge from another model family.
- **Feedback:** answers rated unhelpful show up in the agent desk, which exports them as golden-set candidates.
