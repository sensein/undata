"""Add element_kind, node_kind to data_element; agent_type to user_profile; caused_by_activity_id to audit_log.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-10 00:00:00.000000+00:00

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- data_element: add element_kind and node_kind ---
    op.add_column(
        "data_element",
        sa.Column("element_kind", sa.Text(), nullable=False, server_default="scalar"),
    )
    op.add_column(
        "data_element",
        sa.Column("node_kind", sa.Text(), nullable=False, server_default="field"),
    )

    # Backfill element_kind from current version's allowed_values / data_type.
    # Elements without a current_version_id remain 'scalar' (server_default).
    op.execute(
        """
        UPDATE data_element de
        SET element_kind = CASE
            WHEN dv.allowed_values IS NOT NULL
                 AND jsonb_array_length(dv.allowed_values) > 0 THEN 'enumeration'
            WHEN dv.data_type = 'object' THEN 'complex'
            WHEN dv.data_type = 'array'  THEN 'array'
            ELSE 'scalar'
        END
        FROM data_element_version dv
        WHERE de.current_version_id = dv.id
        """
    )

    # --- user_profile: add agent_type for PROV-DM person vs software agent ---
    op.add_column(
        "user_profile",
        sa.Column("agent_type", sa.Text(), nullable=False, server_default="person"),
    )

    # --- audit_log: add caused_by_activity_id (PROV-DM wasInformedBy chain) ---
    op.add_column(
        "audit_log",
        sa.Column(
            "caused_by_activity_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_audit_log_caused_by",
        "audit_log",
        "audit_log",
        ["caused_by_activity_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_audit_log_caused_by", "audit_log", type_="foreignkey")
    op.drop_column("audit_log", "caused_by_activity_id")
    op.drop_column("user_profile", "agent_type")
    op.drop_column("data_element", "node_kind")
    op.drop_column("data_element", "element_kind")
