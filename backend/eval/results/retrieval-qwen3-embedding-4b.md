## Retrieval: 146 answerable questions (follow-ups excluded), 2026-10-19

Embeddings `qwen3-embedding:4b`, with query instruction. Hit@k = a relevant section is among the top k; MRR@10 = mean of 1/rank of the first relevant section. Query embedding time is not included in ms/query.

| Setup | Hit@1 | Hit@4 | MRR@10 | cross_lingual | german | injection | keyword | market | model | multi_doc | natural | pii | public | version | ms/query |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| dense | 87% | 97% | 0.917 | 75% | 95% | 100% | 92% | 78% | 83% | 67% | 90% | 100% | 62% | 100% | 11 |
| keyword (Postgres full-text) | 38% | 67% | 0.517 | 38% | 55% | 0% | 67% | 44% | 33% | 33% | 32% | 25% | 38% | 0% | 11 |
| hybrid, keyword weight 0.1 | 84% | 95% | 0.901 | 75% | 85% | 100% | 92% | 78% | 83% | 67% | 87% | 100% | 62% | 100% | 10 |
| hybrid, keyword weight 0.5 | 77% | 93% | 0.850 | 62% | 80% | 0% | 92% | 67% | 83% | 67% | 77% | 100% | 50% | 100% | 9 |

Category columns show Hit@1. Not at rank 1 (rank in brackets, None = not in top 10):

- **dense**: uk-008 (8), uk-018 (None), uk-019 (2), uk-027 (3), uk-032 (4), us-004 (5), de-007 (2), dex-002 (2), dex-008 (3), mdl-003 (2), mdl-008 (2), mdl-009 (2), kw-012 (2), mkt-008 (2), mkt-009 (2), pub-004 (2), pub-006 (None), pub-007 (2), md-001 (9)
- **keyword (Postgres full-text)**: uk-001 (None), uk-003 (5), uk-005 (None), uk-006 (3), uk-007 (None), uk-008 (None), uk-009 (None), uk-011 (None), uk-012 (4), uk-013 (None), uk-014 (None), uk-015 (2), uk-016 (5), uk-017 (7), uk-018 (3), uk-019 (2), uk-020 (None), uk-021 (2), uk-023 (7), uk-024 (3), uk-026 (None), uk-027 (8), uk-028 (10), uk-032 (None), uk-033 (None), uk-034 (2), us-001 (10), us-002 (3), us-003 (5), us-004 (3), us-007 (4), us-008 (5), us-009 (2), us-011 (3), us-012 (None), us-016 (3), us-017 (2), us-019 (3), us-020 (2), us-021 (5), us-022 (2), de-001 (5), de-002 (None), de-006 (4), de-007 (None), de-011 (3), de-013 (8), de-016 (None), de-017 (None), de-020 (2), dex-001 (None), dex-003 (None), dex-005 (4), dex-007 (None), dex-008 (None), mdl-004 (3), mdl-005 (2), mdl-006 (2), mdl-007 (4), mdl-008 (3), mdl-009 (None), mdl-011 (4), mdl-013 (2), mdl-015 (2), mdl-016 (None), mdl-017 (7), mdl-018 (3), kw-002 (2), kw-003 (4), kw-005 (2), kw-010 (4), mkt-001 (None), mkt-002 (4), mkt-004 (7), mkt-008 (5), mkt-009 (5), ver-001 (6), ver-002 (6), ver-003 (2), pub-001 (None), pub-004 (None), pub-006 (9), pub-007 (3), pub-008 (2), md-001 (6), md-003 (7), inj-003 (None), pii-001 (4), pii-003 (3), pii-004 (2)
- **hybrid, keyword weight 0.1**: uk-008 (5), uk-014 (2), uk-018 (9), uk-019 (2), uk-027 (3), uk-032 (6), uk-033 (2), us-004 (5), de-002 (7), de-007 (3), de-016 (2), dex-001 (2), dex-008 (3), mdl-003 (2), mdl-008 (2), mdl-009 (2), kw-012 (2), mkt-008 (2), mkt-009 (2), pub-004 (2), pub-006 (8), pub-007 (2), md-001 (8)
- **hybrid, keyword weight 0.5**: uk-001 (2), uk-003 (2), uk-007 (3), uk-008 (6), uk-009 (2), uk-014 (9), uk-018 (8), uk-019 (2), uk-026 (4), uk-027 (2), uk-032 (9), uk-033 (7), us-001 (2), us-004 (5), de-001 (2), de-002 (None), de-007 (3), de-016 (3), dex-001 (3), dex-003 (2), dex-008 (4), mdl-007 (2), mdl-008 (2), mdl-009 (2), kw-003 (2), mkt-002 (2), mkt-008 (2), mkt-009 (2), pub-001 (3), pub-004 (5), pub-006 (5), pub-007 (2), md-001 (9), inj-003 (2)

### Off-topic gate (`dense`, threshold 0.4)

- Answerable questions: top similarity min 0.448, median 0.712; wrongly refused: 0
- Out-of-scope questions refused by the gate: 2 of 10 (oos-007 0.27, oos-002 0.36, oos-010 0.41, oos-001 0.42, oos-006 0.44, oos-003 0.49, oos-004 0.58, oos-009 0.60, oos-005 0.64, oos-008 0.69). The rest must be refused by the grounded answer step.
