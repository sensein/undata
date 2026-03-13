"""Add parent_id, is_mixin, is_system to dynamic_schema for schema inheritance.

Revision ID: 0005
Revises: 0004
Create Date: 2026-03-10 00:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Nullable self-referential FK for single-parent inheritance
    op.add_column(
        "dynamic_schema",
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dynamic_schema.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index("ix_dynamic_schema_parent_id", "dynamic_schema", ["parent_id"])

    # is_mixin: schema can be embedded but not used standalone
    op.add_column(
        "dynamic_schema",
        sa.Column("is_mixin", sa.Boolean(), nullable=False, server_default="false"),
    )

    # is_system: system-reserved schemas (ProvenanceMixin); immutable by non-admin
    op.add_column(
        "dynamic_schema",
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="false"),
    )


def downgrade() -> None:
    op.drop_column("dynamic_schema", "is_system")
    op.drop_column("dynamic_schema", "is_mixin")
    op.drop_index("ix_dynamic_schema_parent_id", table_name="dynamic_schema")
    op.drop_column("dynamic_schema", "parent_id")
