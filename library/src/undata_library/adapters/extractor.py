"""Standard entity extractor from LinkML SchemaDefinition.

All adapters produce a LinkML SchemaDefinition via to_linkml(). This module
provides the standard extraction function that converts SchemaDefinition
to classified entities. No adapter should do its own entity classification.
"""

from __future__ import annotations

from typing import Any

from ..models import SourceRef
from .base import ClassifiedEntity


def extract_from_schema_definition(
    schema_def: Any,
    source_name: str = "linkml",
    source_ref: SourceRef | None = None,
) -> list[ClassifiedEntity]:
    """Extract entities from an in-memory LinkML SchemaDefinition.

    This is THE standard extraction path. All adapters should call this
    after building their SchemaDefinition via to_linkml().

    Delegates to LinkMLAdapter's internal extraction logic.
    """
    from .linkml import LinkMLAdapter

    return LinkMLAdapter().extract_from_schema_definition(
        schema_def, source_name=source_name, source_ref=source_ref
    )
