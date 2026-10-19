"""Hybrid retrieval in one SQL query: dense (pgvector) + keyword (Postgres full-text), fused with RRF.

Filters are applied before ranking: only documents for the customer's market (plus global ones) that are
valid on the query date are searched, and only the newest valid version of each document is used.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

Mode = Literal["hybrid", "dense", "keyword"]
MODES: tuple[Mode, ...] = ("hybrid", "dense", "keyword")
RRF_C = 60  # standard Reciprocal Rank Fusion constant


@dataclass(frozen=True)
class Filters:
    market: str  # "de" | "uk" | "us"; "global" documents are always included
    as_of: date = field(default_factory=date.today)
    source_types: tuple[str, ...] = ("brand", "public")


@dataclass(frozen=True)
class Passage:
    chunk_id: str
    doc_id: str
    path: str
    title: str
    heading_path: tuple[str, ...]
    content: str
    source_type: str
    market: str
    language: str
    url: str | None
    licence: str
    attribution: str | None
    score: float  # fused RRF score, or the reranker's relevance score after reranking
    similarity: float  # cosine similarity between question and chunk embeddings (0..1 in practice)

    @property
    def section(self) -> str:
        return " › ".join(self.heading_path[1:]) or self.title


# Keyword query: OR over the question's stemmed words, parsed with both English and German rules so a
# question in either language can match chunks in either (each chunk's tsvector uses its own language).
_SQL = """
WITH eligible AS (
    SELECT DISTINCT ON (doc_id) path FROM documents
    WHERE market IN (:market, 'global') AND valid_from <= :as_of AND source_type = ANY(:source_types)
    ORDER BY doc_id, valid_from DESC
),
q AS (
    SELECT (
        SELECT string_agg(quote_literal(lexeme), ' | ')
        FROM (
            SELECT unnest(tsvector_to_array(to_tsvector('english', :query))) AS lexeme
            UNION SELECT unnest(tsvector_to_array(to_tsvector('german', :query)))
        ) words
    )::tsquery AS tsq
),
dense AS (
    SELECT c.id, row_number() OVER (ORDER BY c.embedding <=> CAST(:qvec AS vector)) AS rank
    FROM chunks c JOIN eligible e ON e.path = c.document_path
    ORDER BY c.embedding <=> CAST(:qvec AS vector)
    LIMIT :n
),
keyword AS (
    SELECT c.id, row_number() OVER (ORDER BY ts_rank_cd(c.tsv, q.tsq) DESC) AS rank
    FROM chunks c JOIN eligible e ON e.path = c.document_path CROSS JOIN q
    WHERE q.tsq IS NOT NULL AND c.tsv @@ q.tsq
    ORDER BY ts_rank_cd(c.tsv, q.tsq) DESC
    LIMIT :n
),
fused AS (
    SELECT id, sum(weight / (:rrf_c + rank)) AS score FROM (
        SELECT id, rank, :dense_weight AS weight FROM dense
        UNION ALL
        SELECT id, rank, :keyword_weight AS weight FROM keyword
    ) ranked
    GROUP BY id
)
SELECT c.id AS chunk_id, d.doc_id, d.path, d.title, c.heading_path, c.content,
       d.source_type, d.market, d.language,
       d.url, d.licence, d.attribution, f.score,
       1 - (c.embedding <=> CAST(:qvec AS vector)) AS similarity
FROM fused f JOIN chunks c ON c.id = f.id JOIN documents d ON d.path = c.document_path
ORDER BY f.score DESC, c.id
LIMIT :k
"""


def search(
    session: Session,
    query: str,
    query_vector: list[float],
    filters: Filters,
    k: int,
    mode: Mode = "hybrid",
    candidates: int = 30,
    keyword_weight: float = 0.5,
) -> list[Passage]:
    """Top-k passages. `mode` switches either ranker off (weight 0) for evaluation."""
    weights = {"hybrid": (1.0, keyword_weight), "dense": (1.0, 0.0), "keyword": (0.0, 1.0)}[mode]
    rows = session.execute(
        text(_SQL),
        {
            "market": filters.market,
            "as_of": filters.as_of,
            "source_types": list(filters.source_types),
            "query": query,
            "qvec": str(query_vector),
            "n": max(candidates, k),
            "k": k,
            "rrf_c": RRF_C,
            "dense_weight": weights[0],
            "keyword_weight": weights[1],
        },
    )
    return [
        Passage(**{**row, "heading_path": tuple(row["heading_path"]), "similarity": float(row["similarity"])})
        for row in rows.mappings()
        if row["score"] > 0  # a ranker with weight 0 contributes nothing; drop chunks only it found
    ]
