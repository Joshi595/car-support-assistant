"""Incremental indexing: bring the database in line with data/, embedding only what changed.

A document is skipped when its content hash (text + metadata + chunking + embedding model) is unchanged.
For a changed document, chunks are matched by a hash of their text: unchanged chunks keep their vectors,
new ones are embedded, vanished ones are deleted. Documents removed from data/ are deleted with their
chunks. Every run that changes something records a new kb_version, which invalidates the answer cache.
"""

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from car_support.config import get_settings
from car_support.db.models import ChunkRecord, DocumentRecord, KbVersion
from car_support.ingest.catalog import DocMeta, load_catalog
from car_support.ingest.chunk import chunk_markdown, title_of
from car_support.ingest.convert import to_markdown
from car_support.llm import embed_texts

Embedder = Callable[[Sequence[str]], list[list[float]]]


@dataclass(frozen=True)
class IndexReport:
    documents: int
    documents_changed: int
    documents_removed: int
    chunks: int
    chunks_added: int
    chunks_removed: int
    kb_version: int | None


def _sha(*parts: str) -> str:
    return hashlib.sha256("\n".join(parts).encode()).hexdigest()[:32]


def index_corpus(
    session: Session, data_dir: Path, embed: Embedder = embed_texts, *, full: bool = False
) -> IndexReport:
    settings = get_settings()
    chunking = f"{settings.chunk_max_chars}/{settings.chunk_overlap}"
    if full:
        session.execute(delete(DocumentRecord))  # chunks follow via ON DELETE CASCADE

    existing = {d.path: d for d in session.scalars(select(DocumentRecord))}
    changed = added = removed = 0
    for meta in load_catalog(data_dir):
        markdown = to_markdown(data_dir / meta.path)
        doc_hash = _sha(markdown, json.dumps(asdict(meta), default=str), chunking, settings.embed_model)
        record = existing.pop(meta.path, None)
        if record is not None and record.content_hash == doc_hash:
            continue
        changed += 1
        title = title_of(markdown, Path(meta.path).stem)
        session.merge(_document_record(meta, title, doc_hash))

        wanted: dict[str, tuple[int, str, tuple[str, ...]]] = {}
        for chunk in chunk_markdown(markdown, title, settings.chunk_max_chars, settings.chunk_overlap):
            chunk_id = _sha(settings.embed_model, meta.path, chunk.text)
            wanted.setdefault(chunk_id, (len(wanted), chunk.text, chunk.heading_path))
        have = {
            c.id: c
            for c in session.scalars(select(ChunkRecord).where(ChunkRecord.document_path == meta.path))
        }
        for chunk_id, stale in have.items():
            if chunk_id in wanted:
                stale.ordinal = wanted[chunk_id][0]
            else:
                session.delete(stale)
                removed += 1
        new_ids = [i for i in wanted if i not in have]
        vectors = embed([wanted[i][1] for i in new_ids]) if new_ids else []
        session.add_all(
            ChunkRecord(
                id=chunk_id,
                document_path=meta.path,
                ordinal=wanted[chunk_id][0],
                heading_path=list(wanted[chunk_id][2]),
                content=wanted[chunk_id][1],
                language=meta.language,
                embedding=vector,
            )
            for chunk_id, vector in zip(new_ids, vectors, strict=True)
        )
        added += len(new_ids)

    for gone in existing.values():  # files no longer in data/
        removed += (
            session.scalar(
                select(func.count()).select_from(ChunkRecord).where(ChunkRecord.document_path == gone.path)
            )
            or 0
        )
        session.delete(gone)
    session.flush()

    total_docs = session.scalar(select(func.count()).select_from(DocumentRecord)) or 0
    total_chunks = session.scalar(select(func.count()).select_from(ChunkRecord)) or 0
    version = None
    if changed or existing:
        kb = KbVersion(documents=total_docs, chunks=total_chunks, chunks_added=added, chunks_removed=removed)
        session.add(kb)
        session.flush()
        version = kb.id
    session.commit()
    return IndexReport(total_docs, changed, len(existing), total_chunks, added, removed, version)


def _document_record(meta: DocMeta, title: str, content_hash: str) -> DocumentRecord:
    return DocumentRecord(
        path=meta.path,
        doc_id=meta.doc_id,
        source_type=meta.source_type,
        market=meta.market,
        language=meta.language,
        models=list(meta.models),
        title=title,
        valid_from=meta.valid_from,
        licence=meta.licence,
        url=meta.url,
        attribution=meta.attribution,
        content_hash=content_hash,
    )
