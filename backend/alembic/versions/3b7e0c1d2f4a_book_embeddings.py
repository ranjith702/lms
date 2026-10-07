"""book embeddings (pgvector) for semantic search / RAG

Revision ID: 3b7e0c1d2f4a
Revises: 2a1d1455f9c2
Create Date: 2026-10-07

No vector index: pgvector indexes support <= 2000 dims and this model gives 2048.
An exact scan over a few hundred books is ~1 ms. At ~100k books, switch to halfvec + HNSW.
"""
from alembic import op

revision = "3b7e0c1d2f4a"
down_revision = "2a1d1455f9c2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("ALTER TABLE books ADD COLUMN IF NOT EXISTS embedding vector(2048)")
    op.execute("ALTER TABLE books ADD COLUMN IF NOT EXISTS embedding_model varchar(120)")
    op.execute("ALTER TABLE books ADD COLUMN IF NOT EXISTS embedding_hash varchar(64)")


def downgrade() -> None:
    op.execute("ALTER TABLE books DROP COLUMN IF EXISTS embedding_hash")
    op.execute("ALTER TABLE books DROP COLUMN IF EXISTS embedding_model")
    op.execute("ALTER TABLE books DROP COLUMN IF EXISTS embedding")
