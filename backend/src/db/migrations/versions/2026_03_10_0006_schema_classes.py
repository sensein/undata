"""Create schema_class_inheritance and schema_enumeration tables.

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-10 00:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- schema_class_inheritance ---
    # Records is_a / mixin inheritance between class-node DataElements.
    op.create_table(
        "schema_class_inheritance",
        sa.Column(
            "parent_class_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_element.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "child_class_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_element.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "relationship_type",
            sa.Text(),
            nullable=False,
            server_default="is_a",
        ),
        sa.PrimaryKeyConstraint("parent_class_id", "child_class_id"),
    )
    op.create_index(
        "ix_sci_child_class_id",
        "schema_class_inheritance",
        ["child_class_id"],
    )

    # --- schema_enumeration ---
    # First-class rows for enumeration values; supersedes allowed_values JSONB
    # for element_kind='enumeration' elements.
    op.create_table(
        "schema_enumeration",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            nullable=False,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "element_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_element.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("element_id", "value", name="uq_schema_enum_element_value"),
    )
    op.create_index(
        "ix_schema_enum_element_id",
        "schema_enumeration",
        ["element_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_schema_enum_element_id", table_name="schema_enumeration")
    op.drop_table("schema_enumeration")
    op.drop_index("ix_sci_child_class_id", table_name="schema_class_inheritance")
    op.drop_table("schema_class_inheritance")
