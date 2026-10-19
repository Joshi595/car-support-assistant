"""Knowledge-base tables: documents, chunks (pgvector + full-text) and kb_versions.

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-19
"""

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from car_support.db.models import EMBED_DIM, TSV_EXPRESSION

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "documents",
        sa.Column("path", sa.String(), primary_key=True),
        sa.Column("doc_id", sa.String(), nullable=False, index=True),
        sa.Column("source_type", sa.String(), nullable=False),
        sa.Column("market", sa.String(), nullable=False, index=True),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("models", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("licence", sa.String(), nullable=False),
        sa.Column("url", sa.String()),
        sa.Column("attribution", sa.String()),
        sa.Column("content_hash", sa.String(), nullable=False),
        sa.Column("indexed_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "chunks",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column(
            "document_path",
            sa.String(),
            sa.ForeignKey("documents.path", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.Column("heading_path", postgresql.ARRAY(sa.String()), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("language", sa.String(), nullable=False),
        sa.Column("embedding", Vector(EMBED_DIM), nullable=False),
        sa.Column("tsv", postgresql.TSVECTOR(), sa.Computed(TSV_EXPRESSION, persisted=True)),
    )
    op.create_index(
        "ix_chunks_embedding_hnsw",
        "chunks",
        ["embedding"],
        postgresql_using="hnsw",
        postgresql_ops={"embedding": "vector_cosine_ops"},
    )
    op.create_index("ix_chunks_tsv", "chunks", ["tsv"], postgresql_using="gin")
    op.create_table(
        "kb_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("documents", sa.Integer(), nullable=False),
        sa.Column("chunks", sa.Integer(), nullable=False),
        sa.Column("chunks_added", sa.Integer(), nullable=False),
        sa.Column("chunks_removed", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("kb_versions")
    op.drop_table("chunks")
    op.drop_table("documents")
