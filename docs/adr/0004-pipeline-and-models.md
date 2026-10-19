# ADR 0004: Pipeline: one "understand" call, deterministic routing guards, local model by default

**Status:** accepted (Phase 4)

## Context

The prototype ran `condense → retrieve → generate` for every message. Production needs more paths: knowledge-base answers, two live tools (NHTSA recalls, chargers near a place), handoff to a human, and refusals. It must answer in the customer's language and for the customer's market, survive model failures, and run on free models: a 4B model locally, or a free cloud tier.

## Decision

```
understand ─┬─ question ──────► retrieve ─┬─ relevant ──► generate ─► validate
            ├─ recall_lookup ─► recall    └─ off-topic ─► refuse
            ├─ charger_search ► chargers
            ├─ human_agent ───► handoff
            └─ off_topic ─────► off_topic
```

1. **One structured "understand" call per message** returns the intent, the standalone question (follow-ups resolved from a transcript, as in the prototype) and the tool arguments (VIN, make, model, year, location), with the JSON schema enforced by Ollama or Groq. A separate condense call plus a router call would double the latency for no measured gain.
2. **The model decides what it is good at; code decides what code is better at:**
   - *Language* is detected with a word-list heuristic, not by the model. Asked to report it, gemma3:4b labelled English questions German after seeing one German example.
   - *VINs* are matched with a regex. The model's VIN is discarded unless it is a valid 17-character VIN.
   - *Tool arguments are checked before a tool runs.* A recall lookup without a vehicle, or a charger search without a place, becomes a normal question. The documents explain how recalls and charging work, which beats asking the customer for details.
   - *Tool fields are required-but-nullable in the schema.* With optional fields, gemma3:4b left them out and every recall lookup asked for details the customer had already given (recall routing 20% → 100%).
3. **Grounded generation with validation.** The answer prompt carries the customer's market and language. Citations are normalised (gpt-oss writes `【1】`, some models use narrow no-break spaces and hyphens) and invalid ones removed. An answer that cites nothing is replaced by the refusal: no uncited claims reach the customer.
4. **Failures degrade, never crash.** Each model call is retried once (a crashed local Ollama runner restarts on the next request), then tries the fallback chain (`CS_FALLBACK_CHAT_MODEL`, comma-separated). If everything fails, the customer gets "service unavailable, shall I connect you with a colleague?". The understand step falls back to rules, and tools fail with `ToolUnavailableError`.
5. **Models.** `ollama:gemma3:4b` stays the default: local, free, no quota. `groq:openai/gpt-oss-120b` (open weights, Apache-2.0) is the optional cloud model, at `reasoning_effort=low`.
6. **Memory on a 6 GB GPU.** Query embeddings run on the CPU (`CS_QUERY_EMBEDDING_ON_CPU=true`, about 0.5 s) so that gemma3:4b stays resident on the GPU. Swapping the two models cost 5–10 s per question; with both resident, a knowledge-base answer takes 1.6–2.8 s.

## Evaluation (184 golden questions, deterministic grading)

| Chat model | Routed | Correct | Cites relevant | Latency |
|---|---|---|---|---|
| **gemma3:4b** (local, default) | **95%** | **86%** | **87%** | 1.6–2.8 s with both models resident |
| gpt-oss-120b (Groq free tier), before the Phase 4 fixes | 93% | 79% | 90% | median 6.9 s |

Per category for gemma3:4b: recall and charger tools, out-of-scope refusals, version questions, cross-lingual and public-document questions 100%; German 95%; natural 83%; multi-part 0% (refused as a whole). Before the fixes in this phase, the same model scored 91% / 83% / 88%, with tool routing at 20–40%. Full report: [`backend/eval/results/answers-ollama-gemma3-4b.md`](../../backend/eval/results/answers-ollama-gemma3-4b.md).

*Correct* requires every expected fact and no forbidden fact. The grader normalises number formats ("100.000" = "100 000" = "100,000"), Unicode spaces and hyphens; the golden set lists equivalent phrasings ("15p|15 pence"). Answer quality beyond facts (faithfulness, helpfulness) is judged by an LLM in Phase 9.

## Consequences

- **Free-tier quota:** Groq's free tier allows 200,000 tokens per model per day. One full evaluation uses about 220,000, so cloud evaluations run in halves (`eval/run.py answers --part 1/2`, then `--part 2/2`). A public demo answers about 150 questions per day per model; a fallback chain over three Groq models roughly triples that. Spreading load over several accounts to evade limits is not done: it would break the provider's terms.
- **Memory:** the full local stack (Postgres, 4B embedder, 4B chat model) needs about 16 GB RAM with little else running. On smaller machines use `qwen3-embedding:0.6b` or a cloud chat model.
- **Known weaknesses of the 4B model**, to watch in the LLM-judge evaluation: multi-part questions are often refused as a whole, it occasionally picks a figure from the wrong row (a plan price for another model), and it answers some prompt-injection attempts. The last one is addressed by the guardrails in Phase 6.
- **Charger search** needs a free Open Charge Map key; without it, charger questions get the "unavailable, shall I connect you?" reply.
