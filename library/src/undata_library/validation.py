"""Validate YAML files against v2 content-addressed models."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import ElementRecord, SchemaRecord, ValidationReport, ValidationViolation


def validate_file(path: Path) -> ValidationReport:
    """Validate a single YAML file as an ElementRecord or SchemaRecord."""
    violations: list[ValidationViolation] = []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return ValidationReport(
            valid=False, path=str(path),
            violations=[ValidationViolation(field="file", message=str(exc))],
        )

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return ValidationReport(
            valid=False, path=str(path),
            violations=[ValidationViolation(field="yaml", message=str(exc))],
        )

    if not isinstance(data, dict):
        return ValidationReport(
            valid=False, path=str(path),
            violations=[ValidationViolation(field="root", message="YAML root must be a mapping")],
        )

    if "semantic" not in data:
        return ValidationReport(
            valid=False, path=str(path),
            violations=[ValidationViolation(field="root", message="Missing 'semantic' block")],
        )

    # Detect record type from semantic block structure
    semantic = data.get("semantic", {})
    if "properties" in semantic:
        model_cls = SchemaRecord
    elif "data_type" in semantic or "ontology_term" in semantic:
        model_cls = ElementRecord
    else:
        return ValidationReport(
            valid=False, path=str(path),
            violations=[ValidationViolation(
                field="semantic",
                message="Cannot determine record type: need 'data_type' (element) or 'properties' (schema)",
            )],
        )

    try:
        model_cls.model_validate(data)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            violations.append(ValidationViolation(field=loc, message=err["msg"]))

    return ValidationReport(valid=len(violations) == 0, path=str(path), violations=violations)


def validate_directory(directory: Path) -> list[ValidationReport]:
    """Validate all .yaml/.yml files in a directory (recursive)."""
    reports: list[ValidationReport] = []
    seen: set[str] = set()
    for pattern in ("*.yaml", "*.yml"):
        for path in sorted(directory.rglob(pattern)):
            if str(path) not in seen:
                seen.add(str(path))
                reports.append(validate_file(path))
    return reports
