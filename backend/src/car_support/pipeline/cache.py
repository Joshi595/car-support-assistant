"""Exact-match answer cache for knowledge-base answers.

The key covers everything that can change an answer: the normalised standalone question, market, language,
the date (documents have validity dates), the index version and the chat model. Re-indexing or switching
models therefore invalidates old entries without a purge; stale rows can be deleted at leisure.
"""

import hashlib
import json
from datetime import date
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from car_support.config import get_settings
from car_support.db.models import CachedAnswer, KbVersion


def cache_key(question: str, market: str, language: str, as_of: date, session: Session) -> str:
    kb_version = session.scalar(select(func.max(KbVersion.id))) or 0
    normalized = " ".join(question.lower().split()).rstrip("?!. ")
    parts = [normalized, market, language, as_of.isoformat(), kb_version, get_settings().chat_model]
    return hashlib.sha256(json.dumps(parts).encode()).hexdigest()


def lookup(session: Session, key: str) -> CachedAnswer | None:
    hit = session.get(CachedAnswer, key)
    if hit is not None:
        session.execute(
            update(CachedAnswer).where(CachedAnswer.key == key).values(hits=CachedAnswer.hits + 1)
        )
        session.commit()
    return hit


def store(session: Session, key: str, answer: str, sources: list[dict[str, Any]]) -> None:
    session.merge(CachedAnswer(key=key, answer=answer, citations=sources))
    session.commit()
