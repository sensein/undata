"""Seed ProvenanceMixin system DynamicSchema and its 4 DataElements.

Revision ID: 0009
Revises: 0008
Create Date: 2026-03-10 00:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0009"
down_revision: Union[str, None] = "0008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Fixed deterministic UUIDs so this migration is idempotent and re-runnable.
_SCHEMA_ID = "00000000-0000-0000-0000-000000000001"
_ELEM_CREATED_BY = "00000000-0000-0000-0000-000000000011"
_ELEM_CREATED_AT = "00000000-0000-0000-0000-000000000012"
_ELEM_MODIFIED_AT = "00000000-0000-0000-0000-000000000013"
_ELEM_DERIVED_FROM = "00000000-0000-0000-0000-000000000014"

# URIs follow the existing UNDATA_BASE_URL/{type}/{uuid} scheme but use
# a canonical well-known path so they are stable across environments.
_SCHEMA_URI = "https://undata.io/schema/00000000-0000-0000-0000-000000000001"


def upgrade() -> None:
    conn = op.get_bind()

    # Look up the canonical 'undata' SchemaSource id (seeded at app startup).
    result = conn.execute(
        sa.text("SELECT id FROM schema_source WHERE name = 'undata' LIMIT 1")
    )
    row = result.fetchone()
    if row is None:
        # Source not yet seeded (e.g. fresh DB with no app startup).  Insert it.
        conn.execute(
            sa.text(
                """
                INSERT INTO schema_source (id, name, format, content_hash, ingested_at, is_active, version_num)
                VALUES (gen_random_uuid(), 'undata', 'canonical', 'seeded', now(), true, 1)
                ON CONFLICT (name) DO NOTHING
                """
            )
        )
        result = conn.execute(
            sa.text("SELECT id FROM schema_source WHERE name = 'undata' LIMIT 1")
        )
        row = result.fetchone()

    source_id = str(row[0])

    # --- Insert ProvenanceMixin DynamicSchema (idempotent) ---
    conn.execute(
        sa.text(
            """
            INSERT INTO dynamic_schema
                (id, uri, name, description, version_num, is_mixin, is_system, created_at, updated_at)
            VALUES
                (:schema_id, :uri, 'ProvenanceMixin',
                 'System mixin providing standard W3C PROV-DM provenance fields.',
                 1, true, true, now(), now())
            ON CONFLICT (id) DO NOTHING
            """
        ),
        {"schema_id": _SCHEMA_ID, "uri": _SCHEMA_URI},
    )

    # --- Insert 4 DataElements ---
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
        # Insert DataElement stub (no current_version_id yet — set after version insert)
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
            {
                "id": elem["id"],
                "uri": elem["uri"],
                "source_id": source_id,
                "source_local_id": elem["source_local_id"],
            },
        )

        # Insert DataElementVersion
        conn.execute(
            sa.text(
                """
                INSERT INTO data_element_version
                    (id, element_id, version_num, name, data_type, description,
                     required, multivalued, created_at, created_by)
                SELECT
                    gen_random_uuid(), :element_id, 1, :name, :data_type, :description,
                    :required, false, now(),
                    (SELECT id FROM user_profile LIMIT 1)
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

        # Update current_version_id on the DataElement
        conn.execute(
            sa.text(
                """
                UPDATE data_element
                SET current_version_id = (
                    SELECT id FROM data_element_version
                    WHERE element_id = :element_id AND version_num = 1
                    LIMIT 1
                )
                WHERE id = :element_id AND current_version_id IS NULL
                """
            ),
            {"element_id": elem["id"]},
        )

        # Link element to ProvenanceMixin DynamicSchema
        conn.execute(
            sa.text(
                """
                INSERT INTO dynamic_schema_element
                    (schema_id, element_id, position)
                VALUES (:schema_id, :element_id, :position)
                ON CONFLICT (schema_id, element_id) DO NOTHING
                """
            ),
            {"schema_id": _SCHEMA_ID, "element_id": elem["id"], "position": i},
        )


def downgrade() -> None:
    conn = op.get_bind()

    # Remove DynamicSchemaElement links
    conn.execute(
        sa.text("DELETE FROM dynamic_schema_element WHERE schema_id = :schema_id"),
        {"schema_id": _SCHEMA_ID},
    )

    # Remove DataElementVersion rows
    for elem_id in [_ELEM_CREATED_BY, _ELEM_CREATED_AT, _ELEM_MODIFIED_AT, _ELEM_DERIVED_FROM]:
        conn.execute(
            sa.text("DELETE FROM data_element_version WHERE element_id = :id"),
            {"id": elem_id},
        )
        conn.execute(
            sa.text("DELETE FROM data_element WHERE id = :id"),
            {"id": elem_id},
        )

    # Remove DynamicSchema
    conn.execute(
        sa.text("DELETE FROM dynamic_schema WHERE id = :schema_id"),
        {"schema_id": _SCHEMA_ID},
    )
