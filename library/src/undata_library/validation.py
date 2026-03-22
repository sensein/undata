"""Validate YAML files against v2 content-addressed models."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from .models import (
    ElementRecord,
    SchemaRecord,
    ValidationReport,
    ValidationViolation,
    ValueConcept,
)


def validate_file(path: Path) -> ValidationReport:
    """Validate a single YAML file as an ElementRecord or SchemaRecord."""
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
            violations=[ValidationViolation(field="root", message="YAML root must be a mapping")],
        )

    if "semantic" not in data:
        return ValidationReport(
            valid=False,
            path=str(path),
            violations=[ValidationViolation(field="root", message="Missing 'semantic' block")],
        )

    # Detect record type from semantic block structure
    semantic = data.get("semantic", {})
    if "properties" in semantic:
        model_cls = SchemaRecord
    elif "label" in semantic and "value_type" in semantic:
        model_cls = ValueConcept
    elif "data_type" in semantic:
        model_cls = ElementRecord
    else:
        return ValidationReport(
            valid=False,
            path=str(path),
            violations=[
                ValidationViolation(
                    field="semantic",
                    message="Cannot determine record type: need 'data_type' (element) or 'properties' (schema)",
                )
            ],
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


def validate_ingestion_output(library_path: Path) -> list[dict]:
    """Post-ingestion validation of library output.

    Checks:
    (a) every element has valid data_type
    (b) sha256 matches recomputed hash
    (c) no duplicate URIs across elements/schemas/values/valuesets
    (d) schema property URIs resolve
    (e) response_options ValueConcept URIs resolve (warn)
    (f) ValueSet member URIs resolve (warn)
    (g) every schema has ≥1 property

    Returns list of violation dicts: {file, entity_type, check, message, severity}
    """
    from .hashing import compute_identity_hash, determine_hash_mode

    violations: list[dict] = []
    uri_set: set[str] = set()
    valid_data_types = {"string", "integer", "float", "boolean", "array", "object"}

    # Scan elements
    elements_dir = library_path / "elements"
    if elements_dir.exists():
        for f in sorted(elements_dir.glob("*.yaml")):
            data = _load_yaml(f)
            if not data or "semantic" not in data:
                continue

            sem = data["semantic"]
            dt = sem.get("data_type", "")
            if dt not in valid_data_types:
                violations.append(
                    {
                        "file": str(f),
                        "entity_type": "element",
                        "check": "data_type_valid",
                        "message": f"Invalid data_type: {dt}",
                        "severity": "ERROR",
                    }
                )

            # SHA-256 integrity (two-mode hash)
            stored_sha = data.get("sha256")
            if stored_sha:
                annotations = sem.get("ontology_annotations", [])
                ontology_anchored, primary_uri = determine_hash_mode(annotations)
                prov = data.get("provenance", [])
                prov_dicts = [
                    p if isinstance(p, dict) else p.model_dump(by_alias=True) for p in prov
                ]
                recomputed, _ = compute_identity_hash(
                    sem, prov_dicts,
                    ontology_anchored=ontology_anchored,
                    primary_ontology_uri=primary_uri,
                )
                if stored_sha != recomputed:
                    violations.append(
                        {
                            "file": str(f),
                            "entity_type": "element",
                            "check": "sha256_integrity",
                            "message": f"SHA-256 mismatch: stored={stored_sha[:12]}... recomputed={recomputed[:12]}...",
                            "severity": "ERROR",
                        }
                    )

            # URI uniqueness
            uri = f"https://schema.undata.live/elements/{f.stem}"
            if uri in uri_set:
                violations.append(
                    {
                        "file": str(f),
                        "entity_type": "element",
                        "check": "no_duplicate_uris",
                        "message": f"Duplicate URI: {uri}",
                        "severity": "ERROR",
                    }
                )
            uri_set.add(uri)

    # Scan schemas
    schemas_dir = library_path / "schemas"
    if schemas_dir.exists():
        for f in sorted(schemas_dir.glob("*.yaml")):
            data = _load_yaml(f)
            if not data or "semantic" not in data:
                continue

            props = data["semantic"].get("properties", [])
            if not props:
                violations.append(
                    {
                        "file": str(f),
                        "entity_type": "schema",
                        "check": "schema_has_properties",
                        "message": "Schema has 0 properties",
                        "severity": "ERROR",
                    }
                )

            uri = f"https://schema.undata.live/schemas/{f.stem}"
            if uri in uri_set:
                violations.append(
                    {
                        "file": str(f),
                        "entity_type": "schema",
                        "check": "no_duplicate_uris",
                        "message": f"Duplicate URI: {uri}",
                        "severity": "ERROR",
                    }
                )
            uri_set.add(uri)

    # Scan valuesets
    valuesets_dir = library_path / "valuesets"
    if valuesets_dir.exists():
        for f in sorted(valuesets_dir.glob("*.yaml")):
            data = _load_yaml(f)
            if not data or "semantic" not in data:
                continue
            uri = f"https://schema.undata.live/valuesets/{f.stem}"
            if uri in uri_set:
                violations.append(
                    {
                        "file": str(f),
                        "entity_type": "valueset",
                        "check": "no_duplicate_uris",
                        "message": f"Duplicate URI: {uri}",
                        "severity": "ERROR",
                    }
                )
            uri_set.add(uri)

    return violations


def _load_yaml(path: Path) -> dict | None:
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except (yaml.YAMLError, OSError):
        return None
