"""Retrieval: embed the question, then search the customer's market (see ADR 0003 for the choices)."""

from sqlalchemy.orm import Session

from car_support.config import get_settings
from car_support.llm import embed_queries
from car_support.retrieval.search import Filters, Mode, Passage, search

__all__ = ["Filters", "Passage", "is_relevant", "retrieve"]


def retrieve(
    session: Session,
    query: str,
    filters: Filters,
    k: int | None = None,
    mode: Mode | None = None,
    query_vector: list[float] | None = None,
) -> list[Passage]:
    settings = get_settings()
    vector = query_vector if query_vector is not None else embed_queries([query])[0]
    return search(
        session,
        query,
        vector,
        filters,
        k or settings.top_k,
        mode or settings.retrieval_mode,
        settings.candidates,
        settings.keyword_weight,
    )


def is_relevant(passages: list[Passage], threshold: float | None = None) -> bool:
    """False when even the closest passage is far from the question: clearly off-topic, refuse cheaply.

    A conservative pre-filter only. Questions that sound in-domain but are not answered by the documents
    ("What is the drag coefficient?") pass it and are refused by the grounded answer step instead.
    """
    limit = get_settings().relevance_threshold if threshold is None else threshold
    return bool(passages) and max(p.similarity for p in passages) >= limit
