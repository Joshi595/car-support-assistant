# ADR 0007: Deployment: containers and Compose; public demo through a Cloudflare quick tunnel

**Status:** accepted (Phase 10). Replaces the plan's demo on Hugging Face Spaces + Vercel + Neon.

## Context

The plan called for a local stack started with one command, plus a free public demo: frontend on Vercel, API on a Hugging Face Docker Space, database on Neon, LLM on Groq. Its zero-cost rule says to re-check every external service before use and to drop any that needs payment. That re-check (2026-10-20) found:

- **Hugging Face:** "Gradio and Docker Spaces run on compute and require a paid plan to create" ([Spaces overview](https://huggingface.co/docs/hub/en/spaces-overview)). Only static Spaces stay free, and the API needs a server.
- **Render** free web services have 512 MB RAM ([comparison](https://agentdeals.dev/netlify-vs-render)), far too little for the embedding model, and users report card verification ([forum](https://community.render.com/t/free-but-credit-card-first/24630)). Fly.io, Railway and the cloud providers' free tiers need a card.
- **Neon** (free, no card, pgvector, 1 GB per project; [pricing](https://neon.com/pricing), [changelog](https://neon.com/docs/changelog/2026-10-02)) and **Vercel Hobby** (free for non-commercial use) are still free, but without a free API host they cannot form a demo on their own.

## Decision

1. **Images:** `backend/Dockerfile` (multi-stage with uv, slim Python, non-root uid 1000, knowledge base baked in, migrations at start) and `frontend/Dockerfile` (Next.js standalone output, non-root). Base images and tools are pinned to exact versions.
2. **One origin:** the browser talks only to the web app. `src/app/backend/[...path]` forwards the customer routes (chat with streaming, feedback, handoff, conversations) to the API and nothing else; agent routes keep going through the signed-in `/api/agent` path. This removes CORS, and one public address is enough. The API trusts `X-Forwarded-For` only from configured proxies (`CS_FORWARDED_ALLOW_IPS`), so rate limits stay per customer.
3. **Compose:** `docker compose up -d` gives Postgres alone, for development. `--profile app` adds the API and web containers, `--profile observability` adds Phoenix, Prometheus and Grafana, and `--profile ollama` runs Ollama in a container. Ollama runs on the host by default, where GPU access is simplest.
4. **Public demo:** `cloudflared tunnel --url http://localhost:3000` publishes the running stack at a random `https://…trycloudflare.com` address, with no account and no card. The models stay local or on Groq's free tier as configured.

## Consequences

- The demo is online only while the machine runs it, and its address changes on each start. Cloudflare offers quick tunnels without uptime guarantees. A stable address needs a free Cloudflare account and a domain name, which costs money, so that is out of scope.
- If an always-on demo is ever needed and allowed to cost a little, the images already fit a container host: API + Neon + Vercel, or one small VM with the Compose stack.
- One origin also simplifies a real deployment behind a single reverse proxy or ingress.
