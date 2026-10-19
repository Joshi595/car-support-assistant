# ADR 0001: Postgres + pgvector as the single data store

**Status:** accepted (Phase 2)

## Context

The prototype kept vectors in an embedded Chroma database and the BM25 keyword index in the memory of the app process. That works for one process on a laptop, but not in production:

- Several API replicas would each build and hold their own keyword index, which must be rebuilt on every content change.
- Conversations, feedback, tickets and the answer cache need a transactional database anyway.
- Metadata filters (market, language, validity date) must apply to *both* search methods consistently.
- Everything must be free and self-hostable, and the public demo needs a free managed option.

## Decision

Use **one Postgres 16 database with the pgvector extension** for the knowledge base and all application data.

- `chunks.embedding vector(1024)` with an HNSW index (`vector_cosine_ops`) for dense search.
- `chunks.tsv`, a generated `tsvector` column with a GIN index, for keyword search. The text-search configuration follows the chunk's language (`german` or `english`), so German words are stemmed correctly.
- `documents` holds the metadata used for filtering; `kb_versions` records every index change.
- The schema is managed with Alembic migrations.

## Consequences

- The API is stateless: any replica can serve any request, and a re-index is visible to all of them immediately.
- Dense and keyword search, filters and joins can run in a single SQL query (Phase 3).
- Postgres full-text ranking (`ts_rank`) is not BM25. Phase 3 measures whether keyword retrieval quality holds up against the prototype's numbers. If it does not, the fallback is ParadeDB `pg_search` (real BM25 inside Postgres), and Qdrant as a second option.
- The vector dimension (1024) is fixed in the schema. Switching to an embedding model with another dimension requires a migration.
- Free hosting: the `pgvector/pgvector` image locally, Neon's free tier (pgvector supported, no card) for the demo.
