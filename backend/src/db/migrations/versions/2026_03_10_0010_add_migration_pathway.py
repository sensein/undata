"""Add migration_pathway table for 004-migration-api.

Revision ID: 0010
Revises: 0009
Create Date: 2026-03-10 00:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

revision: str = "0010"
down_revision: Union[str, None] = "0009"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "migration_pathway",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("source_schema_id", UUID(as_uuid=True), nullable=False),
        sa.Column("target_schema_id", UUID(as_uuid=True), nullable=False),
        sa.Column("direction", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default="active"),
        sa.Column(
            "inverse_pathway_id",
            UUID(as_uuid=True),
            sa.ForeignKey("migration_pathway.id"),
            nullable=True,
        ),
        sa.Column("steps", JSONB, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("version_num", sa.Integer, nullable=False, server_default="0"),
    )
    op.create_index(
        "ix_migration_pathway_source_schema_id",
        "migration_pathway",
        ["source_schema_id"],
    )
    op.create_index(
        "ix_migration_pathway_target_schema_id",
        "migration_pathway",
        ["target_schema_id"],
    )
    op.create_index(
        "ix_migration_pathway_status",
        "migration_pathway",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_migration_pathway_status", table_name="migration_pathway")
    op.drop_index("ix_migration_pathway_target_schema_id", table_name="migration_pathway")
    op.drop_index("ix_migration_pathway_source_schema_id", table_name="migration_pathway")
    op.drop_table("migration_pathway")
