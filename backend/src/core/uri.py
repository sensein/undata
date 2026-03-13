"""Persistent URI minting for data elements, mapping functions, and schemas.

URIs are deterministic from UUID and stored immutably at creation time.
This module is importable without app context (no circular imports).
"""

from src.core.config import settings


def mint_element_uri(element_id: str) -> str:
    """Return the persistent URI for a data element.

    Args:
        element_id: UUID string of the element.

    Returns:
        Persistent URI of the form ``{base_url}/elements/{element_id}``.
    """
    return f"{settings.undata_base_url}/elements/{element_id}"


def mint_mapping_uri(mapping_id: str) -> str:
    """Return the persistent URI for a mapping function.

    Args:
        mapping_id: UUID string of the mapping function.

    Returns:
        Persistent URI of the form ``{base_url}/mappings/{mapping_id}``.
    """
    return f"{settings.undata_base_url}/mappings/{mapping_id}"


def mint_schema_uri(schema_id: str) -> str:
    """Return the persistent URI for a dynamic schema.

    Args:
        schema_id: UUID string of the dynamic schema.

    Returns:
        Persistent URI of the form ``{base_url}/schemas/{schema_id}``.
    """
    return f"{settings.undata_base_url}/schemas/{schema_id}"
