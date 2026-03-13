"""Flattened initial schema — all tables for the undata schema backend.

Revision ID: 0001
Revises: (none)
Create Date: 2026-03-12 00:00:00.000000+00:00

This is the single canonical migration that creates the complete database
schema from scratch, including all features through 011-metamodel-provenance.
Replace this file (keeping revision="0001", down_revision=None) whenever a
new feature adds columns or tables.
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# ---------------------------------------------------------------------------
# Deterministic UUIDs for seeded system data (ProvenanceMixin)
# ---------------------------------------------------------------------------
_PROV_SCHEMA_ID = "00000000-0000-0000-0000-000000000001"
_ELEM_CREATED_BY = "00000000-0000-0000-0000-000000000011"
_ELEM_CREATED_AT = "00000000-0000-0000-0000-000000000012"
_ELEM_MODIFIED_AT = "00000000-0000-0000-0000-000000000013"
_ELEM_DERIVED_FROM = "00000000-0000-0000-0000-000000000014"
_PROV_SCHEMA_URI = "https://undata.io/schema/00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Extensions
    # ------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    # ------------------------------------------------------------------
    # user_profile
    # ------------------------------------------------------------------
    op.create_table(
        "user_profile",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("external_sub", sa.Text(), nullable=False),
        sa.Column("external_iss", sa.Text(), nullable=False),
        sa.Column("email", sa.Text(), nullable=False),
        sa.Column("display_name", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("agent_type", sa.Text(), nullable=False, server_default="'person'"),
        sa.UniqueConstraint("external_sub", "external_iss", name="uq_user_profile_sub_iss"),
    )

    # ------------------------------------------------------------------
    # api_key
    # ------------------------------------------------------------------
    op.create_table(
        "api_key",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("user_profile.id"), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False, unique=True),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("scopes", postgresql.JSONB(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("user_profile.id"), nullable=True),
    )
    op.create_index("ix_api_key_user_id", "api_key", ["user_id"])

    # ------------------------------------------------------------------
    # user_role
    # ------------------------------------------------------------------
    op.create_table(
        "user_role",
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("user_profile.id"), primary_key=True),
        sa.Column("role", sa.String(50), primary_key=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("user_profile.id"), nullable=False),
    )
    op.create_index("ix_user_role_user_id", "user_role", ["user_id"])

    # ------------------------------------------------------------------
    # schema_source
    # ------------------------------------------------------------------
    op.create_table(
        "schema_source",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=False, unique=True),
        sa.Column("format", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=True),
        sa.Column("version_tag", sa.Text(), nullable=True),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column("version_num", sa.Integer(), nullable=False, server_default="1"),
    )

    # ------------------------------------------------------------------
    # source_membership
    # ------------------------------------------------------------------
    op.create_table(
        "source_membership",
        sa.Column("user_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("user_profile.id"), primary_key=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("schema_source.id"), primary_key=True),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("granted_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("user_profile.id"), nullable=False),
    )
    op.create_index("ix_source_membership_user_source", "source_membership",
                    ["user_id", "source_id"])

    # ------------------------------------------------------------------
    # dynamic_schema  (created before data_element so schema_ref FK works)
    # ------------------------------------------------------------------
    op.create_table(
        "dynamic_schema",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("uri", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("version_num", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("superseded_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("dynamic_schema.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("parent_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("dynamic_schema.id"), nullable=True),
        sa.Column("is_mixin", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.create_index("ix_dynamic_schema_uri", "dynamic_schema", ["uri"], unique=True)
    op.create_index("ix_dynamic_schema_superseded_by", "dynamic_schema", ["superseded_by"])

    # ------------------------------------------------------------------
    # data_element  (references dynamic_schema via schema_ref)
    # ------------------------------------------------------------------
    op.create_table(
        "data_element",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("uri", sa.Text(), nullable=False, unique=True),
        sa.Column("source_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("schema_source.id"), nullable=True),
        sa.Column("source_local_id", sa.Text(), nullable=False),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version_num", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("superseded_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("data_element.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("element_kind", sa.Text(), nullable=False, server_default="'scalar'"),
        sa.Column("node_kind", sa.Text(), nullable=False, server_default="'field'"),
        sa.Column("schema_ref", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("dynamic_schema.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("source_id", "source_local_id", name="uq_data_element_source_local"),
    )
    op.create_index("ix_data_element_uri", "data_element", ["uri"], unique=True)
    op.create_index("ix_data_element_source_id", "data_element", ["source_id"])
    op.create_index("ix_data_element_superseded_by", "data_element", ["superseded_by"])
    op.create_index("ix_data_element_active", "data_element", ["deleted_at"],
                    postgresql_where=sa.text("deleted_at IS NULL"))

    # ------------------------------------------------------------------
    # data_element_version
    # ------------------------------------------------------------------
    op.create_table(
        "data_element_version",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("element_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("data_element.id"), nullable=False),
        sa.Column("version_num", sa.Integer(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("data_type", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("required", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("multivalued", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("allowed_values", postgresql.JSONB(), nullable=True),
        sa.Column("constraints", postgresql.JSONB(), nullable=True),
        sa.Column("semantic_graph", postgresql.JSONB(), nullable=True),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column("name_embedding", postgresql.JSONB(), nullable=True),
        sa.Column("description_embedding", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("user_profile.id"), nullable=False),
    )
    op.create_index("ix_dev_unit", "data_element_version", ["unit"])
    op.create_index("ix_dev_semantic_graph", "data_element_version", ["semantic_graph"],
                    postgresql_using="gin",
                    postgresql_ops={"semantic_graph": "jsonb_path_ops"})

    # Now add the FK from data_element.current_version_id → data_element_version.id
    op.create_foreign_key(
        "fk_data_element_current_version",
        "data_element", "data_element_version",
        ["current_version_id"], ["id"],
    )

    # ------------------------------------------------------------------
    # data_element_child
    # ------------------------------------------------------------------
    op.create_table(
        "data_element_child",
        sa.Column("parent_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("data_element.id"), primary_key=True),
        sa.Column("child_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("data_element.id"), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("field_name", sa.Text(), nullable=False),
    )
    op.create_index("ix_dec_parent_id", "data_element_child", ["parent_id"])
    op.create_index("ix_dec_child_id", "data_element_child", ["child_id"])

    # ------------------------------------------------------------------
    # mapping_function
    # ------------------------------------------------------------------
    op.create_table(
        "mapping_function",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("uri", sa.Text(), nullable=False, unique=True),
        sa.Column("function_type", sa.String(50), nullable=False),
        sa.Column("output_element_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("data_element.id"), nullable=True),
        sa.Column("current_version_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("version_num", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="'active'"),
        sa.Column("attributed_to", sa.Text(), nullable=True),
        sa.Column("confidence_score", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_mapping_function_uri", "mapping_function", ["uri"], unique=True)

    # ------------------------------------------------------------------
    # mapping_input
    # ------------------------------------------------------------------
    op.create_table(
        "mapping_input",
        sa.Column("mapping_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("mapping_function.id"), primary_key=True),
        sa.Column("element_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("data_element.id"), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
    )
    op.create_index("ix_mapping_input_element_id", "mapping_input", ["element_id"])

    # ------------------------------------------------------------------
    # mapping_function_version
    # ------------------------------------------------------------------
    op.create_table(
        "mapping_function_version",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("mapping_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("mapping_function.id"), nullable=False),
        sa.Column("version_num", sa.Integer(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("expression", sa.Text(), nullable=True),
        sa.Column("expression_type", sa.String(50), nullable=False),
        sa.Column("parameter_schema", postgresql.JSONB(), nullable=True),
        sa.Column("inverse_mapping_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("mapping_function.id"), nullable=True),
        sa.Column("sssom_predicate", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("user_profile.id"), nullable=False),
    )
    op.create_index("ix_mfv_created_by", "mapping_function_version", ["created_by"])

    # Add FK from mapping_function.current_version_id → mapping_function_version.id
    op.create_foreign_key(
        "fk_mapping_function_current_version",
        "mapping_function", "mapping_function_version",
        ["current_version_id"], ["id"],
    )

    # ------------------------------------------------------------------
    # alias_group
    # ------------------------------------------------------------------
    op.create_table(
        "alias_group",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=True),
        sa.Column("sssom_predicate", sa.Text(), nullable=False,
                  server_default="'skos:exactMatch'"),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("detection_method", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )

    # ------------------------------------------------------------------
    # alias_group_member
    # ------------------------------------------------------------------
    op.create_table(
        "alias_group_member",
        sa.Column("alias_group_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("alias_group.id"), primary_key=True),
        sa.Column("element_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("data_element.id"), primary_key=True),
    )

    # ------------------------------------------------------------------
    # dynamic_schema_element
    # ------------------------------------------------------------------
    op.create_table(
        "dynamic_schema_element",
        sa.Column("schema_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("dynamic_schema.id"), primary_key=True),
        sa.Column("element_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("data_element.id"), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("field_alias", sa.Text(), nullable=True),
    )
    op.create_index("ix_dse_schema_id", "dynamic_schema_element", ["schema_id"])
    op.create_index("ix_dse_element_id", "dynamic_schema_element", ["element_id"])

    # ------------------------------------------------------------------
    # audit_log
    # ------------------------------------------------------------------
    op.create_table(
        "audit_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("record_type", sa.String(100), nullable=False),
        sa.Column("record_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(20), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("user_profile.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("version_num", sa.Integer(), nullable=True),
        sa.Column("diff", postgresql.JSONB(), nullable=True),
        sa.Column("caused_by_activity_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("audit_log.id"), nullable=True),
    )
    op.create_index("ix_audit_log_record", "audit_log", ["record_type", "record_id"])
    op.create_index("ix_audit_log_actor_id", "audit_log", ["actor_id"])
    op.create_index("ix_audit_log_timestamp", "audit_log", ["timestamp"])

    # ------------------------------------------------------------------
    # schema_class_inheritance
    # ------------------------------------------------------------------
    op.create_table(
        "schema_class_inheritance",
        sa.Column("parent_class_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("data_element.id"), primary_key=True),
        sa.Column("child_class_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("data_element.id"), primary_key=True),
        sa.Column("relationship_type", sa.Text(), nullable=False, server_default="'is_a'"),
    )

    # ------------------------------------------------------------------
    # schema_enumeration
    # ------------------------------------------------------------------
    op.create_table(
        "schema_enumeration",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("element_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("data_element.id"), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("label", sa.Text(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.UniqueConstraint("element_id", "value", name="uq_schema_enum_element_value"),
    )

    # ------------------------------------------------------------------
    # validation_rule
    # ------------------------------------------------------------------
    op.create_table(
        "validation_rule",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("element_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("data_element.id"), nullable=False),
        sa.Column("rule_type", sa.Text(), nullable=False),
        sa.Column("rule_value", postgresql.JSONB(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False, server_default="'error'"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("created_by", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("user_profile.id"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )

    # ------------------------------------------------------------------
    # validation_rule_change
    # ------------------------------------------------------------------
    op.create_table(
        "validation_rule_change",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("rule_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("validation_rule.id"), nullable=False),
        sa.Column("element_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("data_element.id"), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("old_value", postgresql.JSONB(), nullable=True),
        sa.Column("new_value", postgresql.JSONB(), nullable=True),
        sa.Column("breaking", sa.Boolean(), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("user_profile.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("reason", sa.Text(), nullable=True),
    )

    # ------------------------------------------------------------------
    # schema_mixin
    # ------------------------------------------------------------------
    op.create_table(
        "schema_mixin",
        sa.Column("schema_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("dynamic_schema.id"), primary_key=True),
        sa.Column("mixin_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("dynamic_schema.id"), primary_key=True),
        sa.Column("position", sa.Integer(), nullable=False),
    )

    # ------------------------------------------------------------------
    # schema_change_log
    # ------------------------------------------------------------------
    op.create_table(
        "schema_change_log",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("schema_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("dynamic_schema.id"), nullable=False),
        sa.Column("version_num", sa.Integer(), nullable=False),
        sa.Column("operation", sa.Text(), nullable=False),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("user_profile.id"), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("activity_type", sa.Text(), nullable=False),
        sa.Column("diff", postgresql.JSONB(), nullable=True),
        sa.Column("breaking", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("semantic_boundary_crossed", sa.Boolean(), nullable=False,
                  server_default="false"),
        sa.Column("reason", sa.Text(), nullable=True),
    )

    # ------------------------------------------------------------------
    # migration_pathway
    # ------------------------------------------------------------------
    op.create_table(
        "migration_pathway",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("source_schema_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("target_schema_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("direction", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="'active'"),
        sa.Column("inverse_pathway_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("migration_pathway.id"), nullable=True),
        sa.Column("steps", postgresql.JSONB(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("version_num", sa.Integer(), nullable=False, server_default="0"),
    )

    # ------------------------------------------------------------------
    # Seed: ProvenanceMixin system schema + 4 elements
    # ------------------------------------------------------------------
    conn = op.get_bind()

    # Insert undata canonical source (idempotent)
    conn.execute(
        sa.text(
            """
            INSERT INTO schema_source (id, name, format, content_hash, ingested_at, is_active, version_num)
            VALUES (gen_random_uuid(), 'undata', 'canonical', 'seeded', now(), true, 1)
            ON CONFLICT (name) DO NOTHING
            """
        )
    )
    result = conn.execute(sa.text("SELECT id FROM schema_source WHERE name = 'undata' LIMIT 1"))
    source_id = str(result.fetchone()[0])

    # Insert a bootstrap system user so data_element_version.created_by FK is satisfiable
    conn.execute(
        sa.text(
            """
            INSERT INTO user_profile
                (id, external_sub, external_iss, email, display_name, is_active, agent_type)
            VALUES
                ('00000000-0000-0000-0000-000000000000',
                 'system', 'https://undata.io', 'system@undata.io', 'System', true, 'system')
            ON CONFLICT DO NOTHING
            """
        )
    )

    # Insert ProvenanceMixin DynamicSchema
    conn.execute(
        sa.text(
            """
            INSERT INTO dynamic_schema
                (id, uri, name, description, version_num, is_mixin, is_system, created_at, updated_at)
            VALUES
                (:schema_id, :uri, 'ProvenanceMixin',
                 'System mixin providing standard W3C PROV-O provenance fields.',
                 1, true, true, now(), now())
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"schema_id": _PROV_SCHEMA_ID, "uri": _PROV_SCHEMA_URI},
    )

    elements = [
        {
            "id": _ELEM_CREATED_BY,
            "source_local_id": "prov_created_by",
            "uri": f"https://undata.io/element/{_ELEM_CREATED_BY}",
            "data_type": "string",
            "required": True,
            "description": "prov:wasAttributedTo — actor ID or display name",
        },
        {
            "id": _ELEM_CREATED_AT,
            "source_local_id": "prov_created_at",
            "uri": f"https://undata.io/element/{_ELEM_CREATED_AT}",
            "data_type": "string",
            "required": True,
            "description": "prov:generatedAtTime — ISO 8601 timestamp",
        },
        {
            "id": _ELEM_MODIFIED_AT,
            "source_local_id": "prov_modified_at",
            "uri": f"https://undata.io/element/{_ELEM_MODIFIED_AT}",
            "data_type": "string",
            "required": False,
            "description": "prov:invalidatedAtTime — ISO 8601 timestamp",
        },
        {
            "id": _ELEM_DERIVED_FROM,
            "source_local_id": "prov_derived_from",
            "uri": f"https://undata.io/element/{_ELEM_DERIVED_FROM}",
            "data_type": "string",
            "required": False,
            "description": "prov:wasDerivedFrom — source URI or ID",
        },
    ]

    for i, elem in enumerate(elements):
        conn.execute(
            sa.text(
                """
                INSERT INTO data_element
                    (id, uri, source_id, source_local_id, version_num,
                     element_kind, node_kind, created_at)
                VALUES
                    (:id, :uri, :source_id, :source_local_id, 1,
                     'scalar', 'field', now())
                ON CONFLICT (id) DO NOTHING
                """
            ),
            {"id": elem["id"], "uri": elem["uri"],
             "source_id": source_id, "source_local_id": elem["source_local_id"]},
        )
        conn.execute(
            sa.text(
                """
                INSERT INTO data_element_version
                    (id, element_id, version_num, name, data_type, description,
                     required, multivalued, created_at, created_by)
                SELECT
                    gen_random_uuid(), :element_id, 1, :name, :data_type, :description,
                    :required, false, now(), '00000000-0000-0000-0000-000000000000'
                WHERE NOT EXISTS (
                    SELECT 1 FROM data_element_version
                    WHERE element_id = :element_id AND version_num = 1
                )
                """
            ),
            {
                "element_id": elem["id"],
                "name": elem["source_local_id"],
                "data_type": elem["data_type"],
                "description": elem["description"],
                "required": elem["required"],
            },
        )
        conn.execute(
            sa.text(
                """
                UPDATE data_element
                SET current_version_id = (
                    SELECT id FROM data_element_version
                    WHERE element_id = :element_id AND version_num = 1 LIMIT 1
                )
                WHERE id = :element_id AND current_version_id IS NULL
                """
            ),
            {"element_id": elem["id"]},
        )
        conn.execute(
            sa.text(
                """
                INSERT INTO dynamic_schema_element (schema_id, element_id, position)
                VALUES (:schema_id, :element_id, :position)
                ON CONFLICT (schema_id, element_id) DO NOTHING
                """
            ),
            {"schema_id": _PROV_SCHEMA_ID, "element_id": elem["id"], "position": i},
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Remove seed data first (FK order)
    conn.execute(sa.text(
        "DELETE FROM dynamic_schema_element WHERE schema_id = :id"),
        {"id": _PROV_SCHEMA_ID})
    for eid in [_ELEM_CREATED_BY, _ELEM_CREATED_AT, _ELEM_MODIFIED_AT, _ELEM_DERIVED_FROM]:
        conn.execute(sa.text(
            "UPDATE data_element SET current_version_id = NULL WHERE id = :id"), {"id": eid})
        conn.execute(sa.text(
            "DELETE FROM data_element_version WHERE element_id = :id"), {"id": eid})
        conn.execute(sa.text(
            "DELETE FROM data_element WHERE id = :id"), {"id": eid})
    conn.execute(sa.text(
        "DELETE FROM dynamic_schema WHERE id = :id"), {"id": _PROV_SCHEMA_ID})
    conn.execute(sa.text(
        "DELETE FROM user_profile WHERE id = '00000000-0000-0000-0000-000000000000'"))
    conn.execute(sa.text(
        "DELETE FROM schema_source WHERE name = 'undata'"))

    # Drop tables in reverse FK order
    for table in [
        "migration_pathway", "schema_change_log", "schema_mixin",
        "validation_rule_change", "validation_rule", "schema_enumeration",
        "schema_class_inheritance", "audit_log", "dynamic_schema_element",
        "alias_group_member", "alias_group", "mapping_function_version",
        "mapping_input", "mapping_function", "data_element_child",
        "data_element_version", "data_element", "dynamic_schema",
        "source_membership", "schema_source", "user_role", "api_key",
        "user_profile",
    ]:
        op.drop_table(table)

    op.execute("DROP EXTENSION IF EXISTS vector")
    op.execute("DROP EXTENSION IF EXISTS pgcrypto")
