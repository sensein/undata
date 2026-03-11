"""Create validation_rules and validation_rule_changes tables.

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-10 00:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- validation_rules ---
    op.create_table(
        "validation_rule",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "element_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_element.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("rule_type", sa.Text(), nullable=False),
        sa.Column("rule_value", postgresql.JSONB(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False, server_default="error"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_profile.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    # Unique active rule per type per element (partial unique index)
    op.create_index(
        "ix_validation_rule_element_type_active",
        "validation_rule",
        ["element_id", "rule_type"],
        unique=True,
        postgresql_where=sa.text("deleted_at IS NULL"),
    )
    op.create_index("ix_validation_rule_element_id", "validation_rule", ["element_id"])

    # --- validation_rule_changes ---
    op.create_table(
        "validation_rule_change",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "rule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("validation_rule.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "element_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_element.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("old_value", postgresql.JSONB(), nullable=True),
        sa.Column("new_value", postgresql.JSONB(), nullable=True),
        sa.Column("breaking", sa.Boolean(), nullable=False),
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
        sa.Column("reason", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_validation_rule_change_rule_id", "validation_rule_change", ["rule_id"]
    )
    op.create_index(
        "ix_validation_rule_change_element_id",
        "validation_rule_change",
        ["element_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_validation_rule_change_element_id",
        table_name="validation_rule_change",
    )
    op.drop_index(
        "ix_validation_rule_change_rule_id",
        table_name="validation_rule_change",
    )
    op.drop_table("validation_rule_change")
    op.drop_index("ix_validation_rule_element_id", table_name="validation_rule")
    op.drop_index(
        "ix_validation_rule_element_type_active", table_name="validation_rule"
    )
    op.drop_table("validation_rule")
