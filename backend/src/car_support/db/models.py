"""Tables: the knowledge base (documents, chunks, index versions) and the support conversations
(conversations, messages, feedback, handoff tickets, answer cache)."""

import uuid
from datetime import date, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, BigInteger, Computed, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from car_support.db.session import Base

EMBED_DIM = 1024  # Qwen3-Embedding output size requested from Ollama; another size needs a migration

# Full-text config per chunk language, so German text is stemmed as German ("Garantien" → "garanti").
TSV_EXPRESSION = (
    "to_tsvector(CASE language WHEN 'de' THEN 'german'::regconfig ELSE 'english'::regconfig END, content)"
)


class DocumentRecord(Base):
    __tablename__ = "documents"

    path: Mapped[str] = mapped_column(primary_key=True)  # relative to the data dir; one row per version file
    doc_id: Mapped[str] = mapped_column(index=True)  # shared by all versions of one document
    source_type: Mapped[str]
    market: Mapped[str] = mapped_column(index=True)
    language: Mapped[str]
    models: Mapped[list[str]] = mapped_column(ARRAY(String))
    title: Mapped[str]
    valid_from: Mapped[date]
    licence: Mapped[str]
    url: Mapped[str | None]
    attribution: Mapped[str | None]
    content_hash: Mapped[str]  # changes when the text, metadata, chunking or embedding model change
    indexed_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class ChunkRecord(Base):
    __tablename__ = "chunks"

    id: Mapped[str] = mapped_column(primary_key=True)  # hash of embedding model + document path + text
    document_path: Mapped[str] = mapped_column(ForeignKey("documents.path", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int]  # position in the document
    heading_path: Mapped[list[str]] = mapped_column(ARRAY(String))
    content: Mapped[str]  # "Title › Section\nbody", exactly what was embedded
    language: Mapped[str]
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBED_DIM))
    tsv: Mapped[str] = mapped_column(TSVECTOR, Computed(TSV_EXPRESSION, persisted=True))


class KbVersion(Base):
    """One row per ingestion run that changed something; the latest id keys the answer cache."""

    __tablename__ = "kb_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    documents: Mapped[int]
    chunks: Mapped[int]
    chunks_added: Mapped[int]
    chunks_removed: Mapped[int]


# ── Support conversations ──────────────────────────────────────────────────────


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)  # also the customer's handle
    market: Mapped[str]
    status: Mapped[str] = mapped_column(default="open")  # open | handed_off | closed
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    role: Mapped[str]  # user | assistant
    content: Mapped[str]  # personal data redacted before storage
    outcome: Mapped[str | None]  # assistant messages: answer | refuse | recall | handoff | ...
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    model: Mapped[str | None]
    latency_ms: Mapped[int | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Feedback(Base):
    __tablename__ = "feedback"
    __table_args__ = (UniqueConstraint("message_id"),)  # one rating per answer; a new rating replaces it

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    message_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("messages.id", ondelete="CASCADE"))
    rating: Mapped[int]  # +1 or -1
    comment: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Ticket(Base):
    """A conversation handed to a human agent."""

    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), unique=True
    )
    reason: Mapped[str]  # customer_request | refusal | negative_feedback | unavailable
    status: Mapped[str] = mapped_column(default="open", index=True)  # open | in_progress | resolved
    assigned_to: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class CachedAnswer(Base):
    """Answers to identical standalone questions; the key includes the kb_version, so re-indexing
    invalidates every entry without a purge."""

    __tablename__ = "answer_cache"

    key: Mapped[str] = mapped_column(primary_key=True)  # sha256(question, market, language, kb, model)
    answer: Mapped[str]
    citations: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    hits: Mapped[int] = mapped_column(default=0)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
