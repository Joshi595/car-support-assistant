# ADR 0003: Retrieval: dense search with qwen3-embedding:4b, no reranker, off-topic gate

**Status:** accepted (Phase 3). Supersedes the plan's "hybrid + FlashRank reranker" design, because the evaluation contradicted it.

## Context

The production corpus is far harder than the prototype's: 408 chunks instead of 30, three markets with deliberately conflicting facts, German and English documents, and long GOV.UK pages. The plan assumed hybrid search (vector + keyword, fused with RRF) plus a cross-encoder reranker whose score would also decide when to refuse. Every option was measured on the 146 answerable golden questions (follow-ups excluded until the condense step exists) and the 10 out-of-scope ones. Full reports: [`backend/eval/results/`](../../backend/eval/results/).

## Measurements

| Embeddings | Setup | Hit@1 | Hit@4 | MRR@10 | Search time |
|---|---|---|---|---|---|
| qwen3-embedding:0.6b | dense | 71% | 92% | 0.810 | |
| | hybrid (keyword weight 0.5) | 71% | 92% | 0.809 | |
| | hybrid + FlashRank MiniLM-L-12 (English) | 77% | 91% | 0.835 | ~0.9 s |
| | hybrid + FlashRank MultiBERT-L-12 (multilingual) | 36% | 64% | 0.508 | ~1.9 s |
| **qwen3-embedding:4b** | **dense** | **87%** | **97%** | **0.917** | 11 ms |
| | dense, no query instruction | 77% | 94% | 0.849 | |
| | hybrid (keyword weight 0.1) | 84% | 95% | 0.901 | |
| | hybrid (keyword weight 0.5) | 77% | 93% | 0.850 | |
| | keyword only (Postgres full-text) | 38% | 67% | 0.517 | |
| | hybrid + MiniLM-L-12 / MultiBERT-L-12 | 78% / 36% | 91% / 62% | | 1.3 s / 2.2 s |

## Decisions

1. **Embedding model `qwen3-embedding:4b`**, asked for 1024-dimensional vectors (Qwen3-Embedding is Matryoshka-trained, so a shorter prefix of its vector is still a good embedding). That keeps the `vector(1024)` schema, the HNSW index limit of 2,000 dimensions, and the storage size unchanged. It is 16 points better at rank 1 than the 0.6B model. `qwen3-embedding:0.6b` remains a supported setting for machines with little memory.
2. **The query instruction stays.** Qwen3-Embedding is trained with a task instruction on the query side; leaving it out costs 10 points of Hit@1.
3. **Dense search is the default.** With the 4B model, keyword search adds noise: every keyword weight lowered Hit@1, and on keyword-style queries ("SOS button", "V2L") dense alone already reaches 92%. The hybrid SQL stays available (`CS_RETRIEVAL_MODE=hybrid`, weight 0.1), because it costs nothing and may pay off for exact part numbers or codes in a larger corpus.
4. **No reranker.** The English cross-encoder gave +1 point at 120× the latency and hurt German questions. The multilingual one was harmful, and its scores were saturated around 0.999, so they were useless as a refusal signal. FlashRank was removed.
5. **Off-topic gate on cosine similarity, threshold 0.40.** If no retrieved passage reaches 0.40, the question is clearly off-topic and the assistant refuses without calling the chat model. The lowest answerable question scores 0.448 (a bare keyword query, "LL-26 0W-20"), so the gate wrongly refuses none of them. It catches only obviously unrelated questions (2 of 10 in the set, such as pizza and football). In-domain questions that the documents do not answer ("What is the Ion 4's drag coefficient?", 0.69) look exactly like real ones to any similarity score, so refusing them stays the job of the grounded answer step (Phase 4).
6. **`127.0.0.1` instead of `localhost`** for Ollama and Postgres. On Windows, `localhost` resolves to IPv6 first, and each new HTTP connection waited about 2 s before falling back. A query embedding went from 2.3 s to 74 ms.

## Consequences

- Retrieval: Hit@4 is 97%, so the chat model receives a relevant passage for nearly every answerable question. A question takes about 74 ms to embed plus about 11 ms to search.
- Memory: the 4B embedding model needs about 3.4 GB of GPU memory, the same as gemma3:4b. On a 6 GB laptop GPU, Ollama cannot keep both resident, so Phase 4 measures the swap cost end to end. The fallbacks are the 0.6B embedder or a cloud chat model.
- Re-indexing with another embedding model re-embeds everything automatically, because chunk IDs include the model name (about 2.5 minutes here).
- Known weak spots, to revisit with real questions: the public GOV.UK pages (62% at rank 1), where long guides compete with each other, and cross-lingual questions (75%).

## Update (Phase 9): the off-topic threshold depends on the embedding model

The CI retrieval gate indexes with `qwen3-embedding:0.6b`, and there the 0.40 threshold wrongly refused 3 answerable questions: the smaller model's similarities run lower (lowest answerable 0.303 vs 0.448). The threshold is therefore no longer a single number but a per-model default measured on the golden set (`RELEVANCE_THRESHOLDS` in `config.py`: 0.40 for 4B, 0.28 for 0.6B). An unmeasured model gets no gate; the grounded answer step still refuses. `CS_RELEVANCE_THRESHOLD` overrides it.
