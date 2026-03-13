"""Fix schema_source metadata column name.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-08 00:00:00.000000+00:00

"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Rename metadata_ to metadata in schema_source
    # The ORM model uses mapped_column("metadata", ...) but migration created metadata_
    op.alter_column("schema_source", "metadata_", new_column_name="metadata")


def downgrade() -> None:
    op.alter_column("schema_source", "metadata", new_column_name="metadata_")
