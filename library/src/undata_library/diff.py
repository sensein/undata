"""Version diff engine for element and mapping records."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .models import ElementRecord


class FieldDiff:
    """A single field change between two versions."""

    def __init__(self, field: str, old_value: Any, new_value: Any, breaking: bool = False):
        self.field = field
        self.old_value = old_value
        self.new_value = new_value
        self.breaking = breaking

    def to_dict(self) -> dict[str, Any]:
        return {
            "field": self.field,
            "old_value": self.old_value,
            "new_value": self.new_value,
            "breaking": self.breaking,
        }


COMPARE_FIELDS = [
    "name",
    "data_type",
    "description",
    "required",
    "multivalued",
    "allowed_values",
    "constraints",
]


def diff_versions(
    record: ElementRecord,
    from_version: int | None = None,
    to_version: int | None = None,
) -> list[FieldDiff]:
    """Compare two versions of an element, returning field-level diffs.

    If from_version/to_version are not specified, compares the last two versions.
    """
    versions_by_num = {v.version_num: v for v in record.versions}

    if from_version is None or to_version is None:
        nums = sorted(versions_by_num.keys())
        if len(nums) < 2:
            return []
        from_version = nums[-2]
        to_version = nums[-1]

    v_old = versions_by_num.get(from_version)
    v_new = versions_by_num.get(to_version)

    if v_old is None or v_new is None:
        return []

    diffs: list[FieldDiff] = []

    # Check changelog for breaking flag
    breaking_fields: set[str] = set()
    if v_new.changelog:
        for entry in v_new.changelog:
            if entry.breaking:
                breaking_fields.add(entry.change_type)

    for field in COMPARE_FIELDS:
        old_val = getattr(v_old, field, None)
        new_val = getattr(v_new, field, None)

        # Normalize for comparison
        if old_val != new_val:
            is_breaking = bool(breaking_fields)  # any breaking changelog entry
            diffs.append(FieldDiff(field, old_val, new_val, breaking=is_breaking))

    # Check semantic_graph changes
    old_sg = v_old.semantic_graph
    new_sg = v_new.semantic_graph
    if old_sg != new_sg:
        old_dict = old_sg.model_dump() if old_sg else None
        new_dict = new_sg.model_dump() if new_sg else None
        diffs.append(FieldDiff("semantic_graph", old_dict, new_dict))

    return diffs


def diff_file(
    path: Path,
    from_version: int | None = None,
    to_version: int | None = None,
) -> list[FieldDiff]:
    """Load a YAML file and diff its versions."""
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    record = ElementRecord.model_validate(data)
    return diff_versions(record, from_version, to_version)
