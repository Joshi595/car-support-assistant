# ADR 0006: Observability: Prometheus metrics, Phoenix traces, personal data kept out of both

**Status:** accepted (Phase 8)

## Context

To run the assistant you need to answer three kinds of question. *Is it healthy?* (replies, latency, failures). *Why was this answer bad?* (what the question became, which passages were retrieved, what the model saw). *Is it getting better or worse?* (refusals, handoffs, ratings). The tools must be free and self-hostable, and traces must not become a store of customers' personal data.

## Decision

1. **Metrics with `prometheus_client`**, served at `/metrics`, scraped by Prometheus and shown on a provisioned Grafana dashboard (`infra/grafana`). Metrics: replies by outcome and market, reply time, time per pipeline step (every graph node is wrapped by `timed`), cache hits, ratings, handoffs by reason, tool failures, model failures after retries, blocked injection attempts. Labels have small fixed value sets, so the time series stay few.
2. **Traces with OpenTelemetry to a self-hosted Arize Phoenix** (`CS_TRACING_ENDPOINT`, off by default). The OpenInference LangChain instrumentor records every graph step, prompt, model call and retrieval. FastAPI 0.148's built-in telemetry adds the HTTP span, so one customer request is one trace.
3. **Personal data never enters the graph.** The question is redacted (except a VIN, which the recall tool needs) before the pipeline starts, so neither traces nor logs nor models see it. FastAPI's own telemetry "logs" (validation errors with the raw input) are switched off.
4. **Noise is excluded:** `/metrics`, `/healthz` and `/readyz` produce no spans.
5. Phoenix, Prometheus and Grafana run as the Compose profile `observability`, with images pinned to exact versions.

## Evidence

- After a mixed run (answers, a follow-up, a cache hit, a refusal, a blocked injection, German, a recall), the counters reconcile: 7 messages reached the guard, 6 the understand step (one was blocked), 5 the cache (one was a recall), 4 retrieval (one cache hit).
- A message containing an email address and a phone number left **no trace of either in 172 stored spans**; only `[email]` appears.
- After the exclusion, 0 spans were recorded for `/metrics` and the health checks, although Prometheus scrapes every 15 s.

## Consequences

- The dashboard palette is the validated categorical set on Grafana's dark surface, in a fixed order. Status red is reserved for "unavailable", and each panel has one axis.
- Right after an API restart, Prometheus `increase()` undercounts in short ranges, because a new counter's first value precedes the first scrape. It settles after a few minutes; use longer ranges for reporting.
- Phoenix is source-available under the Elastic License 2.0: free to self-host, but not OSI open source. If that matters, any OTLP collector (e.g. Jaeger) can take its place, because the app only speaks OTLP.
- Metrics are per process. With several API replicas, Prometheus scrapes each one; the queries already aggregate with `sum`.
