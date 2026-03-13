"""Initial schema — all 16 tables for Schema Backend Service.

Revision ID: 0001
Revises:
Create Date: 2026-03-08 00:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ------------------------------------------------------------------
    # user_profile
    # ------------------------------------------------------------------
    op.create_table(
        "user_profile",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("external_sub", sa.Text(), nullable=False),
        sa.Column("external_iss", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=True),
        sa.Column("display_name", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("external_sub", "external_iss", name="uq_user_profile_sub_iss"),
    )

    # ------------------------------------------------------------------
    # api_key
    # ------------------------------------------------------------------
    op.create_table(
        "api_key",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_profile.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("scopes", postgresql.JSONB(), nullable=True),
        sa.Column(
            "issued_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "revoked_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_profile.id"),
            nullable=True,
        ),
    )
    op.create_index("ix_api_key_token_hash", "api_key", ["token_hash"], unique=True)
    op.create_index("ix_api_key_user_id", "api_key", ["user_id"])

    # ------------------------------------------------------------------
    # user_role
    # ------------------------------------------------------------------
    op.create_table(
        "user_role",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_profile.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "granted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_profile.id"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("user_id", "role", name="pk_user_role"),
    )
    op.create_index("ix_user_role_user_id", "user_role", ["user_id"])

    # ------------------------------------------------------------------
    # schema_source
    # ------------------------------------------------------------------
    op.create_table(
        "schema_source",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("format", sa.Text(), nullable=True),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("version_tag", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=True),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("metadata_", postgresql.JSONB(), nullable=True),
        sa.Column("version_num", sa.Integer(), nullable=False, server_default="1"),
        sa.UniqueConstraint("name", name="uq_schema_source_name"),
    )

    # ------------------------------------------------------------------
    # source_membership
    # ------------------------------------------------------------------
    op.create_table(
        "source_membership",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_profile.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schema_source.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "granted_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_profile.id"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("user_id", "source_id", name="pk_source_membership"),
    )
    op.create_index(
        "ix_source_membership_user_source", "source_membership", ["user_id", "source_id"]
    )

    # ------------------------------------------------------------------
    # data_element
    # ------------------------------------------------------------------
    op.create_table(
        "data_element",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column(
            "source_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("schema_source.id"),
            nullable=False,
        ),
        sa.Column("source_local_id", sa.Text(), nullable=True),
        sa.Column(
            "current_version_id", postgresql.UUID(as_uuid=True), nullable=True
        ),  # FK added after data_element_version
        sa.Column("version_num", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "superseded_by", postgresql.UUID(as_uuid=True), nullable=True
        ),  # self-FK added below
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("uri", name="uq_data_element_uri"),
        sa.UniqueConstraint("source_id", "source_local_id", name="uq_data_element_source_local"),
    )
    op.create_index("ix_data_element_uri", "data_element", ["uri"])
    op.create_index("ix_data_element_superseded_by", "data_element", ["superseded_by"])
    op.create_index("ix_data_element_source_id", "data_element", ["source_id"])
    # Partial index for active elements only
    op.create_index(
        "ix_data_element_active",
        "data_element",
        ["id"],
        postgresql_where=sa.text("deleted_at IS NULL"),
    )

    # Self-referential FK for superseded_by
    op.create_foreign_key(
        "fk_data_element_superseded_by",
        "data_element",
        "data_element",
        ["superseded_by"],
        ["id"],
    )

    # ------------------------------------------------------------------
    # data_element_version
    # ------------------------------------------------------------------
    op.create_table(
        "data_element_version",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "element_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_element.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_num", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("data_type", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("multivalued", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("allowed_values", postgresql.JSONB(), nullable=True),
        sa.Column("constraints", postgresql.JSONB(), nullable=True),
        sa.Column("semantic_graph", postgresql.JSONB(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column(
            "name_embedding", postgresql.JSONB(), nullable=True
        ),  # VECTOR(384) stored as JSONB; app uses pgvector
        sa.Column("description_embedding", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_profile.id"),
            nullable=True,
        ),
        sa.UniqueConstraint("element_id", "version_num", name="uq_data_element_version"),
    )
    # GIN index on semantic_graph JSONB
    op.create_index(
        "ix_data_element_version_semantic_graph",
        "data_element_version",
        ["semantic_graph"],
        postgresql_using="gin",
        postgresql_ops={"semantic_graph": "jsonb_path_ops"},
    )
    # B-tree index on unit for filtering
    op.create_index("ix_data_element_version_unit", "data_element_version", ["unit"])
    op.create_index("ix_data_element_version_element_id", "data_element_version", ["element_id"])
    # GIN tsvector indexes for full-text search
    op.create_index(
        "ix_data_element_version_name_fts",
        "data_element_version",
        [sa.text("to_tsvector('english', coalesce(name, ''))")],
        postgresql_using="gin",
    )
    op.create_index(
        "ix_data_element_version_description_fts",
        "data_element_version",
        [sa.text("to_tsvector('english', coalesce(description, ''))")],
        postgresql_using="gin",
    )

    # Now add current_version_id FK to data_element (deferred because version table didn't exist yet)
    op.create_foreign_key(
        "fk_data_element_current_version",
        "data_element",
        "data_element_version",
        ["current_version_id"],
        ["id"],
    )

    # ------------------------------------------------------------------
    # data_element_child  (nested element references)
    # ------------------------------------------------------------------
    op.create_table(
        "data_element_child",
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_element.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "child_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_element.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("field_name", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("parent_id", "child_id", name="pk_data_element_child"),
    )
    op.create_index("ix_data_element_child_parent_id", "data_element_child", ["parent_id"])
    op.create_index("ix_data_element_child_child_id", "data_element_child", ["child_id"])

    # ------------------------------------------------------------------
    # mapping_function
    # ------------------------------------------------------------------
    op.create_table(
        "mapping_function",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column("function_type", sa.Text(), nullable=False),
        sa.Column(
            "output_element_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_element.id"),
            nullable=False,
        ),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version_num", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.Text(), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("uri", name="uq_mapping_function_uri"),
    )
    op.create_index("ix_mapping_function_uri", "mapping_function", ["uri"])

    # ------------------------------------------------------------------
    # mapping_input
    # ------------------------------------------------------------------
    op.create_table(
        "mapping_input",
        sa.Column(
            "mapping_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mapping_function.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "element_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_element.id"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("mapping_id", "element_id", name="pk_mapping_input"),
    )
    op.create_index("ix_mapping_input_element_id", "mapping_input", ["element_id"])
    op.create_index("ix_mapping_input_mapping_id", "mapping_input", ["mapping_id"])

    # ------------------------------------------------------------------
    # mapping_function_version
    # ------------------------------------------------------------------
    op.create_table(
        "mapping_function_version",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "mapping_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mapping_function.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("version_num", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("expression", sa.Text(), nullable=True),
        sa.Column("expression_type", sa.Text(), nullable=True),
        sa.Column("parameter_schema", postgresql.JSONB(), nullable=True),
        sa.Column(
            "inverse_mapping_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("mapping_function.id"),
            nullable=True,
        ),
        sa.Column("sssom_predicate", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "created_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_profile.id"),
            nullable=False,
        ),
        sa.UniqueConstraint("mapping_id", "version_num", name="uq_mapping_function_version"),
    )
    op.create_index(
        "ix_mapping_function_version_mapping_id", "mapping_function_version", ["mapping_id"]
    )
    op.create_index("ix_mfv_created_by", "mapping_function_version", ["created_by"])

    # Add FK from mapping_function.current_version_id → mapping_function_version.id
    op.create_foreign_key(
        "fk_mapping_function_current_version",
        "mapping_function",
        "mapping_function_version",
        ["current_version_id"],
        ["id"],
    )

    # ------------------------------------------------------------------
    # alias_group
    # ------------------------------------------------------------------
    op.create_table(
        "alias_group",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("sssom_predicate", sa.Text(), nullable=False, server_default="skos:exactMatch"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("detection_method", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # ------------------------------------------------------------------
    # alias_group_member
    # ------------------------------------------------------------------
    op.create_table(
        "alias_group_member",
        sa.Column(
            "alias_group_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("alias_group.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "element_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_element.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("alias_group_id", "element_id", name="pk_alias_group_member"),
    )
    op.create_index("ix_alias_group_member_element_id", "alias_group_member", ["element_id"])
    op.create_index("ix_alias_group_member_group_id", "alias_group_member", ["alias_group_id"])

    # ------------------------------------------------------------------
    # dynamic_schema
    # ------------------------------------------------------------------
    op.create_table(
        "dynamic_schema",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("uri", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version_num", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "superseded_by", postgresql.UUID(as_uuid=True), nullable=True
        ),  # self-FK added below
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("uri", name="uq_dynamic_schema_uri"),
    )
    op.create_index("ix_dynamic_schema_uri", "dynamic_schema", ["uri"])
    op.create_index("ix_dynamic_schema_superseded_by", "dynamic_schema", ["superseded_by"])

    # Self-referential FK for superseded_by
    op.create_foreign_key(
        "fk_dynamic_schema_superseded_by",
        "dynamic_schema",
        "dynamic_schema",
        ["superseded_by"],
        ["id"],
    )

    # ------------------------------------------------------------------
    # dynamic_schema_element
    # ------------------------------------------------------------------
    op.create_table(
        "dynamic_schema_element",
        sa.Column(
            "schema_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("dynamic_schema.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "element_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("data_element.id"),
            nullable=False,
        ),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("field_alias", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("schema_id", "element_id", name="pk_dynamic_schema_element"),
    )
    op.create_index("ix_dynamic_schema_element_schema_id", "dynamic_schema_element", ["schema_id"])
    op.create_index(
        "ix_dynamic_schema_element_element_id", "dynamic_schema_element", ["element_id"]
    )

    # ------------------------------------------------------------------
    # audit_log
    # ------------------------------------------------------------------
    op.create_table(
        "audit_log",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("record_type", sa.Text(), nullable=False),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column(
            "actor_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("user_profile.id"),
            nullable=False,
        ),
        sa.Column(
            "timestamp", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")
        ),
        sa.Column("version_num", sa.Integer(), nullable=True),
        sa.Column("diff", postgresql.JSONB(), nullable=True),
    )
    op.create_index("ix_audit_log_record", "audit_log", ["record_type", "record_id"])
    op.create_index("ix_audit_log_actor_id", "audit_log", ["actor_id"])
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("dynamic_schema_element")

    op.drop_constraint("fk_dynamic_schema_superseded_by", "dynamic_schema", type_="foreignkey")
    op.drop_table("dynamic_schema")

    op.drop_table("alias_group_member")
    op.drop_table("alias_group")

    op.drop_constraint(
        "fk_mapping_function_current_version", "mapping_function", type_="foreignkey"
    )
    op.drop_table("mapping_function_version")
    op.drop_table("mapping_input")
    op.drop_table("mapping_function")

    op.drop_table("data_element_child")

    op.drop_constraint("fk_data_element_current_version", "data_element", type_="foreignkey")
    op.drop_table("data_element_version")

    op.drop_constraint("fk_data_element_superseded_by", "data_element", type_="foreignkey")
    op.drop_table("data_element")

    op.drop_table("source_membership")
    op.drop_table("schema_source")
    op.drop_table("user_role")
    op.drop_table("api_key")
    op.drop_table("user_profile")

    op.execute("DROP EXTENSION IF EXISTS vector")
