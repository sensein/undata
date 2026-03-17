"""BIDS schema extractor — uses bidsschematools load_code."""

from __future__ import annotations

from ..models import Constraints, ProvenanceEntry, SemanticIdentity

_TYPE_MAP = {
    "string": "string",
    "number": "float",
    "integer": "integer",
    "boolean": "boolean",
    "array": "array",
    "object": "object",
}


def extract_bids() -> list[tuple[SemanticIdentity, ProvenanceEntry]]:
    """Extract elements from BIDS via bidsschematools."""
    try:
        from bidsschematools import schema as bids_schema
    except ImportError as exc:
        raise ImportError(f"bidsschematools required for BIDS extraction: {exc}") from exc

    schema = bids_schema.load_schema()
    results: list[tuple[SemanticIdentity, ProvenanceEntry]] = []

    # bidsschematools returns Namespace objects, not plain dicts
    objects = schema.get("objects", {})
    for cat_name in objects:
        category = objects[cat_name]
        if not hasattr(category, "__iter__"):
            continue
        for field_name in category:
            field_def = category[field_name]
            if not hasattr(field_def, "get"):
                continue
            dt = _bids_type(field_def)
            desc = str(field_def.get("description", "") or "")

            # Extract enum values
            constraints = None
            enum_vals = field_def.get("enum") if hasattr(field_def, "get") else None
            if enum_vals and hasattr(enum_vals, "__iter__"):
                allowed = [str(v) for v in enum_vals if v is not None]
                if allowed:
                    constraints = Constraints(allowed_values=allowed)

            sem = SemanticIdentity(data_type=dt, constraints=constraints)
            prov = ProvenanceEntry(
                source="bids",
                **{"class": cat_name},
                name=field_name,
                description=desc or None,
            )
            results.append((sem, prov))

    return results


def _bids_type(field_def: object) -> str:
    """Extract data type from a BIDS Namespace field definition."""
    t = field_def.get("type", "string") if hasattr(field_def, "get") else "string"
    if isinstance(t, (list, tuple)):
        t = t[0] if t else "string"
    return _TYPE_MAP.get(str(t), "string")
