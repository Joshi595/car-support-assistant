# Car Support Assistant: production build plan

## Context

`car_support_rag` is a working local prototype: a 6-doc knowledge base, Chroma + in-memory BM25 fused with RRF, a LangGraph `condense → retrieve → generate` pipeline, Streamlit, and a 44-question eval. Its README roadmap and chapter 25 of `RAG_Project_Concepts_Guide.pdf` list what production needs: real multi-source data, incremental indexing, metadata filters, reranking, served models, LLM-as-judge in CI, human handoff, tickets, feedback, an API, tracing, dashboards, guardrails and caching.

**Goal:** build a clean, production-grade customer-support assistant. Everything is **free with no payment ever needed** (see the zero-cost policy). It runs fully local with one command and also has a free public demo. Interview constraints no longer apply. The prototype is a reference only: an idea is kept when it earned its place in the eval, and code is not carried over.

Decisions made with you:
- Deploy: local Docker Compose **plus** a free public demo.
- LLM: Ollama by default; one config value switches to a free cloud tier (Groq or Gemini).
- Data: a synthetic fictional-brand corpus **plus** real open data (APIs chosen from the public-apis list where they fit).
- UI: a production web frontend.

## Zero-cost policy (hard rule)

1. **Open source first.** Every component of the local system is open source (or free source-available) and self-hosted. Running it locally needs **no account, no API key, no card**.
2. **Free tiers only where self-hosting is impossible**, which means only for the public demo and optional CI. Allowed only if the free tier **needs no credit card**. Anything that asks for a card is excluded (e.g. Oracle Cloud, Fly.io, Railway, AWS/GCP/Azure free trials).
3. **Every external free service has a local fallback**, so the project keeps working if a free tier changes or disappears.
4. **No paid add-ons:** no custom domain (use `*.vercel.app` / `*.hf.space`), no paid models, no RapidAPI.
5. Before setting up any external service, its current free terms are re-checked. If it now needs a card, it is dropped for its fallback.

| Component | Licence / cost | External? | Fallback |
|---|---|---|---|
| Python, FastAPI, SQLAlchemy, Alembic, LangGraph/LangChain, markitdown, FlashRank | MIT / Apache-2.0 / BSD | No | none needed |
| Postgres 16 + pgvector | PostgreSQL licence | No | none needed |
| Ollama + qwen3-embedding:0.6b (Apache-2.0) + chat model (gemma3:4b, Gemma terms; or an Apache-2.0 model such as granite4 / qwen3-instruct if the eval allows) | Free | No | none needed |
| Next.js, Tailwind, shadcn/ui, Auth.js, Playwright | MIT / ISC / Apache-2.0 | No | none needed |
| Phoenix (Elastic Licence 2.0, free to self-host), Prometheus (Apache-2.0), Grafana (AGPL) | Free | No | none needed |
| Container runtime | Docker Desktop (free for personal use) or Podman (Apache-2.0) | No | Podman |
| Groq / Gemini free tier (no card) | Free tier | Yes | Ollama locally (judge: the largest local model that fits) |
| NHTSA vPIC + Recalls | US gov, no key | Yes | Tool reports "service unavailable" and offers handoff |
| Open Charge Map | Free key, open data | Yes | Same as above |
| GOV.UK Content API (OGL v3) | Free, no key | Fetched once at ingest | Snapshot kept in `data/public/` |
| GitHub + Actions | Free (unlimited minutes on public repos) | Yes | `make ci` runs the same checks locally |
| Demo: Vercel Hobby, Hugging Face CPU Space, Neon free | Free, no card | Yes | Local Compose is the main deliverable; the demo can also run the LLM on Ollama inside the Space (slower, zero third-party APIs) |

## What carries over from the prototype (ideas, not code)

| Idea | Why it stays |
|---|---|
| Structure-aware chunking with a `Title › Section` heading prefix on every chunk | Kept facts with their context; dense Hit@1 was 100% |
| Hybrid retrieval (dense + keyword) fused with RRF | Only mode that was strong on both natural and keyword queries |
| A condense step that rewrites follow-ups, with history given as a transcript | Follow-up Hit@1 went from 2/4 to 4/4; chat-turn format failed with small models |
| Numbered passages, `[n]` citations, only cited sources shown | Makes every answer checkable |
| A fixed, detectable refusal; temperature 0 | Testable refusals and repeatable evals |
| Decisions backed by eval numbers | The working method for the whole build |

Dropped: Chroma, the in-memory BM25 index (it doesn't work with several API replicas), the `Heading:`-format parser, Streamlit, the env-var-only config, keyword-only answer checks, and the prototype repo layout.

## Target architecture

```
Next.js frontend (customer chat · agent desk)          Auth.js (GitHub OAuth) for agents
        │  HTTPS + SSE streaming
FastAPI backend (stateless, horizontally scalable)
        │
        └─► LangGraph pipeline
              guard_input → condense → route ─┬─► retrieve (hybrid SQL + filters) → rerank → gate ─┬─► generate → validate_output
                                              ├─► recall_lookup (NHTSA)                           └─► refuse (no LLM call)
                                              ├─► charger_search (Open Charge Map)
                                              └─► handoff (create ticket)
        ├── Postgres 16 + pgvector: documents, chunks (vector + full-text), conversations, feedback, tickets, answer cache
        ├── Ollama: qwen3-embedding:0.6b + gemma3:4b   (or Groq/Gemini via config)
        ├── Phoenix: traces (OpenTelemetry/OpenInference)
        └── Prometheus + Grafana: metrics dashboards
```

**Technology choices (all free / open source):**

| Concern | Choice | Why |
|---|---|---|
| Language / tooling | Python 3.12, `uv`, ruff, mypy (strict on core), pre-commit | Fast, reproducible, one standard toolchain |
| Config | pydantic-settings | Typed, validated, environment-specific |
| Database | Postgres 16 + pgvector, SQLAlchemy 2 + Alembic | One store for vectors, keywords, metadata filters and app data. Free locally and on Neon's free tier |
| Hybrid search | **One SQL query**: pgvector cosine top-N + Postgres full-text (`tsvector` with `english`/`german` stemming) top-N, fused with RRF in SQL | Stateless API (no per-process index to rebuild), proper stemming per language, filters applied in the same query |
| Ingestion | `markitdown` (MIT) converts PDF/HTML/DOCX/MD → Markdown; split on Markdown headings with a heading-path prefix, then token-bounded recursive splitting | One pipeline for every format; keeps the proven section-aware idea |
| Embeddings | `qwen3-embedding:0.6b` via Ollama | Multilingual (EN/DE), small, proven on this domain |
| Reranker | FlashRank (ONNX cross-encoder, CPU, no torch) | Cheap precision boost; its score drives the relevance gate |
| Orchestration | LangGraph + LangChain `init_chat_model` | Explicit, traceable state machine with routing and tools; provider switch without custom code |
| API | FastAPI, SSE streaming, slowapi rate limits, JWT verification for agent routes | Standard, async, free OpenAPI docs |
| Frontend | Next.js (App Router, TypeScript) + Tailwind + shadcn/ui; Auth.js for the agent desk | Production-grade UI and auth; free hosting on Vercel |
| Tracing | Arize Phoenix (self-hosted, one container) | Free, shows every node, prompt, chunk and score |
| Metrics | Prometheus + Grafana (provisioned dashboard) | Free industry standard |
| Guardrails | Regex PII redaction (email, phone, VIN, IBAN, plates), injection heuristics, output validation | Covers the structured PII that matters; no heavy models |
| Tests | pytest, testcontainers (real Postgres), Playwright for UI smoke tests | Integration tests against the real DB, not mocks |
| CI | GitHub Actions | Free for public repos |

## Repository

A **new repo**, `car-support-assistant` (name is your choice), with clean history. The prototype repo stays untouched as the case-study reference.

```
car-support-assistant/
├── backend/
│   ├── pyproject.toml · uv.lock · Dockerfile · alembic/
│   ├── src/car_support/
│   │   ├── config.py · llm.py · guardrails.py · observability.py
│   │   ├── ingest/      convert.py · chunk.py · index.py (hash-based incremental)
│   │   ├── retrieval/   search.py (hybrid SQL) · rerank.py
│   │   ├── pipeline/    graph.py · prompts.py · tools.py (NHTSA, Open Charge Map)
│   │   ├── db/          models.py · session.py
│   │   └── api/         main.py · routes/ (chat, feedback, handoff, admin, health) · schemas.py · auth.py
│   ├── tests/           unit/ · integration/
│   └── eval/            golden/*.jsonl · run.py · judge.py
├── frontend/            Next.js (customer chat, agent desk)
├── data/
│   ├── brand/<market>/<lang>/…    synthetic "Northwind Motors" docs (md, pdf, html)
│   ├── public/…                   open-licensed docs + SOURCES.md (licence per file)
│   └── scripts/fetch_public.py
├── infra/               compose.yaml · prometheus.yml · grafana/ · demo/
├── docs/                architecture.md · runbook.md · data-sources.md · adr/
└── .github/workflows/   ci.yml · eval-nightly.yml · deploy-demo.yml
```

## Phases

Each phase ends with passing tests, the eval updated where relevant, and its own PR. You can review or reorder phase by phase.

### Phase 0: Foundations
- New repo, `uv` project, ruff/mypy/pre-commit, pydantic-settings, JSON structured logging with request IDs, the Docker Compose skeleton (Postgres + Ollama), and Alembic set up.
- CI skeleton running lint and tests from the first commit.

### Phase 1: Data
- **Synthetic brand corpus** (written by me) for the fictional "Northwind Motors" (you can rename it): about 40–60 docs, 3–4 vehicle models (including EVs), markets DE / UK / US, English + German. Formats: Markdown, PDFs (owner-manual style, with long sections), HTML FAQ pages. Market-specific facts differ on purpose (warranty, hotline, incentives) to test filters. Some docs are versioned (`valid_from`) to test updates.
- **Real open data:**
  - *Live tool:* NHTSA vPIC (VIN decode) + NHTSA Recalls API (US gov, public domain, no key): "is there a recall for my car / VIN?". Presented as a general recall check, never as Northwind data.
  - *Live tool:* Open Charge Map (free key, open data): "where can I charge near X?". Returns real chargers with connector type and power, with attribution in the UI.
  - *Ingested public guidance:* brand-neutral pages on EV charging, consumer rights and vehicle safety from GOV.UK (Open Government Licence v3.0, via its Content API) and US federal sites (public domain). Licence and URL go in the metadata and `SOURCES.md`, and each licence is verified at fetch time.
  - Official endpoints only (no RapidAPI wrappers); tool responses are cached briefly to stay polite to the free services.
- Chunk metadata: `source, source_type (brand|public), market, language, model, title, heading_path, doc_version, valid_from, licence, url, content_hash`.
- **Golden set** (~150 questions): natural, keyword, follow-up, out-of-scope, market-specific (the correct market must win), German, multi-document, tool routing (recall, charger), prompt-injection attempts, PII-containing questions.

### Phase 2: Ingestion and storage
- Schema: `documents`, `chunks` (vector(1024) with an HNSW index, `tsvector` with a GIN index, jsonb metadata), `kb_versions`.
- Incremental indexer: hash each chunk, re-embed only new or changed ones, delete removed ones, bump `kb_version`. CLI: `car-support ingest [--full]`. Idempotent, so a second run does nothing.

### Phase 3: Retrieval
- Hybrid SQL search with metadata filters (market, language, source_type, valid_from ≤ today).
- FlashRank rerank of the top ~30 fused candidates → keep k.
- Relevance gate: if the top rerank score is below a threshold (tuned on the eval), refuse without calling the LLM.
- *Optional (Corrective-RAG idea):* when the gate fails, rewrite the query once and retry before refusing. Kept only if the eval shows a gain.
- Eval: dense vs full-text vs hybrid vs hybrid+rerank, with and without filters. Each choice is justified by numbers in an ADR.
- **Outcome:** the eval overturned the reranker. The final design is dense search with `qwen3-embedding:4b`, no reranker, and an off-topic gate on cosine similarity; see [ADR 0003](adr/0003-retrieval.md).

### Phase 4: Pipeline and models
- `llm.py`: `init_chat_model` from config, with timeouts, retries and a fallback provider (e.g. Groq rate-limited → Ollama).
- Graph: `guard_input → condense → route → {retrieve→rerank→gate→generate→validate_output | recall_lookup | charger_search | handoff | refuse}`. The router is a structured-output LLM call with a rules fallback.
- Answers in the customer's language. Citations are validated: invalid `[n]` are stripped, and an answer with no valid citations gets a safe fallback.
- Eval compares gemma3:4b (local) against a free-tier cloud model.

### Phase 5: Backend API
- `POST /v1/chat` (SSE: tokens → sources/metadata event), `POST /v1/feedback`, `POST /v1/handoff`, `GET /v1/conversations/{id}`. Agent routes (JWT): tickets, feedback, `POST /v1/admin/reindex`. Plus `/healthz`, `/readyz`, `/metrics`.
- Conversations stored with PII redacted. Rate limits on public routes, CORS locked to the frontend origin.
- Answer cache: key = hash(standalone question, market, language, kb_version, model). Re-indexing invalidates it automatically.

### Phase 6: Guardrails
- Input: PII redaction before the LLM, logs and traces; prompt-injection heuristics → safe refusal; length limits.
- Retrieved and tool content is wrapped as data, never as instructions (important now that public web content is ingested).
- Output: citation validation, refusal detection, a system-prompt-leak check.
- The injection and PII eval categories must reach 100%.

### Phase 7: Frontend
- **Customer chat:** streaming answers, clickable citations with passage preview and a source/licence badge, market + language selector, thumbs up/down, "Talk to a human" (offered automatically after a refusal or a thumbs-down), a VIN recall check, and charger results as a list with links.
- **Agent desk** (Auth.js login): ticket queue with transcript and cited sources, feedback list, "promote to golden set" export.
- Accessible, responsive, light and dark theme. Playwright smoke tests.

### Phase 8: Observability
- Phoenix traces for every request: rewritten query, route, retrieved and reranked chunks with scores, prompt, answer, per-node latency.
- Grafana dashboard: p50/p95 latency per node, refusal rate, handoff rate, cache hit rate, feedback ratio, tokens, LLM errors and fallbacks, tool call success.

### Phase 9: Evaluation and CI
- `judge.py`: an LLM-as-judge rubric (faithfulness, correctness, citation support) with structured output, run on a free cloud model. Cheap deterministic checks run first.
- `ci.yml` on every PR: lint, types, unit + integration tests, frontend lint/build, `pip-audit`, `npm audit`, a Trivy image scan, and a **retrieval eval gate** (fail if Hit@k or MRR drops below the thresholds).
- `eval-nightly.yml` (and manual runs): the full end-to-end eval + judge on Groq's free tier, with the report kept as an artifact.

### Phase 10: Deployment and docs
- **Local:** `infra/compose.yaml` starts postgres, ollama (models pulled by an init job), api, frontend, phoenix, prometheus and grafana, all with health checks. `make up / ingest / eval / test`.
- **Free public demo:** frontend on Vercel (Hobby); API on a Hugging Face Docker Space (CPU, with the Ollama embedder inside); Neon free Postgres (pgvector); Groq free-tier LLM. Deployed by `deploy-demo.yml`. Trade-offs: cold starts while the Space or Neon sleeps, and rate limits. The demo shows a "fictional brand data" banner. Free-tier limits are re-checked before setup.
- Docs: README (quick start, architecture, eval results, decisions), `architecture.md`, `runbook.md` (re-index, rotate keys, add a market or language), `data-sources.md`, and ADRs for the main choices.

- **Outcome:** the free-terms re-check found that Hugging Face Docker Spaces now need a paid plan, and that no no-card host fits the API, so by rule 5 the public demo runs on the local stack through a Cloudflare quick tunnel (no account). See [ADR 0007](adr/0007-deployment.md).

### Phase 11: Learning guide, production edition (PDF), written last
- A companion to `RAG_Project_Concepts_Guide.pdf`, in the same style and with the same box types (Key idea, Analogy, In this project, If you are asked, Pitfall), so it reads as "part 2" of that guide.
- It explains **what changed from the prototype to production, how, and why**, chapter by chapter: data and catalog, conversion and chunking, Postgres + pgvector, incremental indexing, hybrid SQL search with filters and versions, embedding-model and reranker choices, the relevance gate, the LangGraph pipeline with router and tools, guardrails, the API, the frontend, observability, LLM-as-judge and CI, deployment and the zero-cost setup.
- Every number comes from this repo's evals, ADRs and live runs (the ADRs and `backend/eval/results/` are the running log it draws on). It covers new concepts from scratch (e.g. Matryoshka embeddings, cross-encoders, SSE streaming, tracing, prompt injection) and ends with a glossary, a command cheat-sheet and likely interview questions with answers.
- Delivered as HTML source in `docs/guide/` and rendered to PDF with headless Edge. A copy goes next to the original guide as `D:\Projects\BMW_RAG_Manideep\RAG_Production_Guide.pdf`.

## Verification (end-to-end)
1. `make test` (unit + integration on real Postgres) and the frontend lint/build/Playwright tests are green; CI passes on every PR.
2. `docker compose up` → all services healthy. `make ingest` indexes both corpora; a second run re-embeds 0 chunks; editing one section re-embeds only that chunk.
3. `make eval` → `eval/results.md`. Targets: retrieval Hit@4 ≥ 95%, judge faithfulness ≥ 95%, market-filter correctness 100%, out-of-scope, injection and PII 100%, and p95 latency recorded.
4. In the UI: a DE and a UK warranty question (different correct answers), a German question, a follow-up, a VIN recall check, "chargers near Munich", an out-of-scope question → handoff → the ticket appears in the agent desk; thumbs-down → it appears in feedback.
5. The Phoenix trace shows every node for those requests; Grafana shows them.
6. The public demo URL answers end-to-end using Groq + Neon.
7. The production guide PDF renders, and every number in it matches `backend/eval/results/` and the ADRs.

## Assumptions you may want to change
- Repo name `car-support-assistant`; brand "Northwind Motors"; markets DE/UK/US; languages EN/DE.
- Postgres full-text search replaces BM25 for the keyword side. If the eval shows a clear drop on keyword queries, the fallback is ParadeDB `pg_search` (real BM25 in Postgres) for local use, or Qdrant.
- Recall and charger lookups are live tools, not ingested data.
- Phase 7 (frontend) can move right after Phase 5 if you want something visible early.
