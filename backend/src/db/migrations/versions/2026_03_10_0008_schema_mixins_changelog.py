"""Create schema_mixin and schema_change_log tables.

Revision ID: 0008
Revises: 0007
Create Date: 2026-03-10 00:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0008"
down_revision: Union[str, None] = "0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- schema_mixin ---
    # M:N join: DynamicSchema (base) ↔ DynamicSchema (mixin), ordered by position.
    op.create_table(
        "schema_mixin",
        sa.Column(
            "schema_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dynamic_schema.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "mixin_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dynamic_schema.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("schema_id", "mixin_id"),
    )
    op.create_index("ix_schema_mixin_schema_id", "schema_mixin", ["schema_id"])
    op.create_index("ix_schema_mixin_mixin_id", "schema_mixin", ["mixin_id"])

    # --- schema_change_log ---
    # Append-only PROV-DM provenance log for every schema-level mutation.
    op.create_table(
        "schema_change_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "schema_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dynamic_schema.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("version_num", sa.Integer(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_profile.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "timestamp",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("activity_type", sa.Text(), nullable=False),
        sa.Column("diff", postgresql.JSONB(), nullable=True),
        sa.Column("breaking", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column(
            "semantic_boundary_crossed",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_schema_change_log_schema_id", "schema_change_log", ["schema_id"])
    op.create_index("ix_schema_change_log_timestamp", "schema_change_log", ["timestamp"])


def downgrade() -> None:
    op.drop_index("ix_schema_change_log_timestamp", table_name="schema_change_log")
    op.drop_index("ix_schema_change_log_schema_id", table_name="schema_change_log")
    op.drop_table("schema_change_log")
    op.drop_index("ix_schema_mixin_mixin_id", table_name="schema_mixin")
    op.drop_index("ix_schema_mixin_schema_id", table_name="schema_mixin")
    op.drop_table("schema_mixin")
