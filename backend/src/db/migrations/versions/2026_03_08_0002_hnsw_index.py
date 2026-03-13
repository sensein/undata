"""Add HNSW vector indexes on data_element_version embeddings.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-08 00:01:00.000000+00:00

Note: HNSW indexes are created CONCURRENTLY so initial schema (0001) must
complete first. On a cold DB the CONCURRENTLY keyword requires the table to
exist and the pgvector extension to be enabled — both handled by 0001.
"""

from typing import Sequence, Union

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # HNSW index on name_embedding (stored as JSONB in migration 0001;
    # actual VECTOR type requires pgvector to cast — skip for now, rely on
    # application-layer cosine similarity until vector column type is used)
    # These are placeholder indexes; full pgvector HNSW requires VECTOR columns.
    # The application layer handles cosine similarity in Python for now.
    #
    # When the column type is migrated from JSONB to VECTOR(384):
    # op.execute("""
    #     CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dev_name_emb
    #     ON data_element_version USING hnsw (name_embedding vector_cosine_ops)
    #     WITH (m=16, ef_construction=64)
    # """)
    # op.execute("""
    #     CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_dev_desc_emb
    #     ON data_element_version USING hnsw (description_embedding vector_cosine_ops)
    #     WITH (m=16, ef_construction=64)
    # """)
    pass


def downgrade() -> None:
    # op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_dev_name_emb")
    # op.execute("DROP INDEX CONCURRENTLY IF EXISTS idx_dev_desc_emb")
    pass
