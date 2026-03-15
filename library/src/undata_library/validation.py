"""Validate YAML files against undata-library Pydantic models."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import ElementRecord, MappingRecord, ValidationReport, ValidationViolation


def validate_file(path: Path) -> ValidationReport:
    """Validate a single YAML file as an ElementRecord or MappingRecord."""
    violations: list[ValidationViolation] = []

    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return ValidationReport(
            valid=False,
            path=str(path),
            violations=[ValidationViolation(field="file", message=str(exc))],
        )

    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        return ValidationReport(
            valid=False,
            path=str(path),
            violations=[ValidationViolation(field="yaml", message=str(exc))],
        )

    if not isinstance(data, dict):
        return ValidationReport(
            valid=False,
            path=str(path),
            violations=[
                ValidationViolation(field="root", message="YAML root must be a mapping")
            ],
        )

    # Detect record type
    if "element" in data:
        model_cls = ElementRecord
    elif "mapping" in data:
        model_cls = MappingRecord
    else:
        return ValidationReport(
            valid=False,
            path=str(path),
            violations=[
                ValidationViolation(
                    field="root",
                    message="YAML must contain 'element' or 'mapping' top-level key",
                )
            ],
        )

    try:
        model_cls.model_validate(data)
    except ValidationError as exc:
        for err in exc.errors():
            loc = ".".join(str(p) for p in err["loc"])
            violations.append(
                ValidationViolation(field=loc, message=err["msg"])
            )

    return ValidationReport(
        valid=len(violations) == 0,
        path=str(path),
        violations=violations,
    )


def validate_directory(directory: Path) -> list[ValidationReport]:
    """Validate all .yaml/.yml files in a directory (recursive)."""
    reports: list[ValidationReport] = []
    for path in sorted(directory.rglob("*.yaml")):
        reports.append(validate_file(path))
    for path in sorted(directory.rglob("*.yml")):
        if not any(r.path == str(path) for r in reports):
            reports.append(validate_file(path))
    return reports
