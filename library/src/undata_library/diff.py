"""Diff provenance entries within an element file (v2 format)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import ElementRecord


def diff_provenance(path: Path) -> list[dict[str, Any]]:
    """Compare provenance entries pairwise within an element file.

    Returns a list of field-level differences between the first two provenance entries.
    """
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    record = ElementRecord.model_validate(data)

    if len(record.provenance) < 2:
        return []

    a = record.provenance[0]
    b = record.provenance[1]

    diffs: list[dict[str, Any]] = []
    for field in ("name", "description", "required", "multivalued"):
        val_a = getattr(a, field)
        val_b = getattr(b, field)
        if val_a != val_b:
            diffs.append({
                "field": field,
                "source_a": a.source,
                "value_a": val_a,
                "source_b": b.source,
                "value_b": val_b,
            })

    return diffs
