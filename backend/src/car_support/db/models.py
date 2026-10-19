"""Knowledge-base tables: documents, their chunks (vector + full-text), and index versions."""

from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import ARRAY, Computed, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column

from car_support.db.session import Base

EMBED_DIM = 1024  # qwen3-embedding:0.6b; changing models with another size needs a migration

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
