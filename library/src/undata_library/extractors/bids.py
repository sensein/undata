"""BIDS schema extractor — uses bidsschematools load_code."""

from __future__ import annotations

from ..models import Constraints, ProvenanceEntry, ResponseOption, SemanticIdentity

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

            # Extract enum values as response_options + legacy constraints
            constraints = None
            response_options = None
            enum_vals = field_def.get("enum") if hasattr(field_def, "get") else None
            if enum_vals and hasattr(enum_vals, "__iter__"):
                allowed = [str(v) for v in enum_vals if v is not None]
                if allowed:
                    constraints = Constraints(allowed_values=allowed)
                    response_options = [ResponseOption(value=v, label=v) for v in allowed]

            # Extract min/max from numeric constraints
            min_value = None
            max_value = None
            if hasattr(field_def, "get"):
                min_val = field_def.get("minimum")
                max_val = field_def.get("maximum")
                if min_val is not None:
                    min_value = float(min_val)
                if max_val is not None:
                    max_value = float(max_val)

            # Determine value_domain
            value_domain = None
            if enum_vals:
                value_domain = "categorical"
            elif dt in ("integer", "float"):
                value_domain = "numeric"
            elif dt == "boolean":
                value_domain = "boolean"
            elif dt == "string":
                value_domain = "text"

            sem = SemanticIdentity(
                data_type=dt,
                constraints=constraints,
                response_options=response_options,
                min_value=min_value,
                max_value=max_value,
                value_domain=value_domain,
            )
            prov = ProvenanceEntry(
                source="bids",
                **{"class": cat_name},
                name=field_name,
                description=desc or None,
            )
            results.append((sem, prov))

    return results


def _bids_type(field_def: object) -> str:
    t = field_def.get("type", "string") if hasattr(field_def, "get") else "string"
    if isinstance(t, (list, tuple)):
        t = t[0] if t else "string"
    return _TYPE_MAP.get(str(t), "string")
