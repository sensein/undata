"""DANDI schema extractor — uses dandischema."""

from __future__ import annotations

from ..models import ProvenanceEntry, SemanticIdentity


def extract_dandi() -> list[tuple[SemanticIdentity, ProvenanceEntry]]:
    """Extract elements from DANDI via dandischema."""
    try:
        import dandischema.models as dm
    except ImportError as exc:
        raise ImportError(f"dandischema required for DANDI extraction: {exc}") from exc

    import inspect

    results: list[tuple[SemanticIdentity, ProvenanceEntry]] = []

    for cls_name, cls in inspect.getmembers(dm, inspect.isclass):
        if not hasattr(cls, "model_fields"):
            continue
        for field_name, field_info in cls.model_fields.items():
            dt = _pydantic_type(field_info)
            desc = field_info.description or ""
            sem = SemanticIdentity(data_type=dt)
            prov = ProvenanceEntry(
                source="dandi",
                **{"class": cls_name},
                name=field_name,
                description=desc,
            )
            results.append((sem, prov))

    return results


def _pydantic_type(field_info) -> str:
    ann = str(field_info.annotation) if field_info.annotation else "string"
    if "int" in ann.lower():
        return "integer"
    if "float" in ann.lower():
        return "float"
    if "bool" in ann.lower():
        return "boolean"
    if "list" in ann.lower():
        return "array"
    return "string"
