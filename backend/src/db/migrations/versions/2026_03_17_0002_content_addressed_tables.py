"""Add content-addressed element, value, schema, mapping tables.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-17

These tables implement the undata-library content-addressed data model.
Old data_element/data_element_version tables are NOT removed — they remain
until data migration (0003) is verified.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Element (content-addressed property)
    op.create_table(
        "element",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("semantic_hash", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("uri", sa.String(255), unique=True, nullable=False),
        sa.Column("semantic", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "element_provenance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "element_id",
            sa.Integer(),
            sa.ForeignKey("element.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("class", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("required", sa.Boolean()),
        sa.Column("multivalued", sa.Boolean()),
        sa.Column("added_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("element_id", "source", "name", name="uq_elem_prov_source_name"),
    )
    op.create_index("ix_elem_prov_element_id", "element_provenance", ["element_id"])

    # Value concept (content-addressed categorical value)
    op.create_table(
        "value_concept",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("semantic_hash", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("uri", sa.String(255), unique=True, nullable=False),
        sa.Column("semantic", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "value_provenance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "value_concept_id",
            sa.Integer(),
            sa.ForeignKey("value_concept.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("raw_value", sa.String(500), nullable=False),
        sa.Column("added_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint(
            "value_concept_id", "source", "raw_value", name="uq_val_prov_source_raw"
        ),
    )

    # Schema shape (content-addressed class shape)
    op.create_table(
        "schema_shape",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("semantic_hash", sa.String(64), unique=True, nullable=False, index=True),
        sa.Column("uri", sa.String(255), unique=True, nullable=False),
        sa.Column("semantic", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "schema_provenance",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "schema_shape_id",
            sa.Integer(),
            sa.ForeignKey("schema_shape.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("added_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint(
            "schema_shape_id", "source", "name", name="uq_schema_prov_source_name"
        ),
    )

    # Element mapping (bidirectional transforms)
    op.create_table(
        "element_mapping",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_element_uri", sa.String(255), nullable=False, index=True),
        sa.Column("target_element_uri", sa.String(255), nullable=False, index=True),
        sa.Column("function_type", sa.String(50), nullable=False),
        sa.Column("expression", sa.Text()),
        sa.Column("expression_type", sa.String(50)),
        sa.Column("sssom_predicate", sa.String(100)),
        sa.Column("confidence", sa.Float()),
        sa.Column("attributed_to", sa.String(255)),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("element_mapping")
    op.drop_table("schema_provenance")
    op.drop_table("schema_shape")
    op.drop_table("value_provenance")
    op.drop_table("value_concept")
    op.drop_index("ix_elem_prov_element_id", table_name="element_provenance")
    op.drop_table("element_provenance")
    op.drop_table("element")
