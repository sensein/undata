"""Extraction validation: compare adapter output against expected entities.

This module provides tools to validate that extraction is complete and
correctly classified. It works iteratively:

1. Extract entities from a source
2. Compare against expected entity counts and classifications
3. Report mismatches, missing entities, misclassified entities
4. Feed results back to refine the adapter

The validation spec for each source defines:
- Expected entity types and approximate counts
- Known categories that should map to specific entity types
- Entities that should NOT be extracted (structural metadata, not data elements)
"""

from __future__ import annotations

import logging
from collections import Counter


logger = logging.getLogger(__name__)


def validate_extraction(
    entities: list,
    source_name: str,
    validation_spec: dict | None = None,
) -> dict:
    """Validate extracted entities against a source-specific spec.

    Args:
        entities: List of ClassifiedEntity objects from adapter.extract()
        source_name: Name of the source (bids, dandi, nwb, openminds, aind)
        validation_spec: Optional spec defining expected entities.
            If None, uses built-in spec for known sources.

    Returns:
        Validation report dict with:
        - entity_counts: {entity_type: count}
        - classification_issues: [{entity, expected_type, actual_type, reason}]
        - missing_entities: [{name, expected_type, reason}]
        - unexpected_entities: [{name, actual_type, reason}]
        - score: float (0.0-1.0, overall extraction quality)
    """
    spec = validation_spec or _get_builtin_spec(source_name)
    if spec is None:
        return {"error": f"No validation spec for source: {source_name}"}

    # Count entities by type
    type_counts = Counter(e.entity_type.value for e in entities)

    # Build entity index by (class, name) for lookup
    entity_index: dict[tuple[str, str], list] = {}
    for e in entities:
        prov = e.provenance if isinstance(e.provenance, dict) else {}
        key = (prov.get("class", ""), prov.get("name", ""))
        entity_index.setdefault(key, []).append(e)

    classification_issues = []
    missing_entities = []
    unexpected_entities = []

    # Check expected entity type distributions
    expected_types = spec.get("expected_types", {})
    for etype, expected_range in expected_types.items():
        actual = type_counts.get(etype, 0)
        min_count = expected_range.get("min", 0)
        max_count = expected_range.get("max", float("inf"))
        if actual < min_count:
            missing_entities.append(
                {
                    "entity_type": etype,
                    "expected_min": min_count,
                    "actual": actual,
                    "reason": f"Expected at least {min_count} {etype} entities, got {actual}",
                }
            )
        elif actual > max_count:
            unexpected_entities.append(
                {
                    "entity_type": etype,
                    "expected_max": max_count,
                    "actual": actual,
                    "reason": f"Expected at most {max_count} {etype} entities, got {actual}",
                }
            )

    # Check category → entity type mappings
    category_rules = spec.get("category_rules", {})
    for e in entities:
        prov = e.provenance if isinstance(e.provenance, dict) else {}
        category = prov.get("class", "")
        if category in category_rules:
            expected_type = category_rules[category]
            if e.entity_type.value != expected_type:
                classification_issues.append(
                    {
                        "name": prov.get("name", ""),
                        "category": category,
                        "expected_type": expected_type,
                        "actual_type": e.entity_type.value,
                        "reason": f"Category '{category}' should produce {expected_type}, got {e.entity_type.value}",
                    }
                )

    # Check for specific known entities
    known_entities = spec.get("known_entities", [])
    for ke in known_entities:
        key = (ke.get("class", ""), ke["name"])
        matches = entity_index.get(key, [])
        if not matches:
            missing_entities.append(
                {
                    "name": ke["name"],
                    "class": ke.get("class", ""),
                    "expected_type": ke.get("type", "any"),
                    "reason": f"Known entity '{ke['name']}' not found in extraction",
                }
            )
        else:
            for m in matches:
                if ke.get("type") and m.entity_type.value != ke["type"]:
                    classification_issues.append(
                        {
                            "name": ke["name"],
                            "class": ke.get("class", ""),
                            "expected_type": ke["type"],
                            "actual_type": m.entity_type.value,
                            "reason": f"Known entity '{ke['name']}' should be {ke['type']}, is {m.entity_type.value}",
                        }
                    )

    # Check semantic fields that should be populated
    field_issues = _check_semantic_fields(entities, spec.get("required_fields", {}))

    # Compute quality score
    total_entities = len(entities)
    issue_count = len(classification_issues) + len(missing_entities) + len(field_issues)
    score = max(0.0, 1.0 - (issue_count / max(total_entities, 1)))

    return {
        "source": source_name,
        "entity_counts": dict(type_counts),
        "total_entities": total_entities,
        "classification_issues": classification_issues,
        "missing_entities": missing_entities,
        "unexpected_entities": unexpected_entities,
        "field_issues": field_issues,
        "issue_count": issue_count,
        "score": round(score, 3),
    }


def _check_semantic_fields(entities: list, required_fields: dict) -> list[dict]:
    """Check that required semantic fields are populated."""
    issues = []
    for e in entities:
        etype = e.entity_type.value
        if etype not in required_fields:
            continue
        sem = e.semantic if isinstance(e.semantic, dict) else {}
        for field in required_fields[etype]:
            if not sem.get(field):
                prov = e.provenance if isinstance(e.provenance, dict) else {}
                issues.append(
                    {
                        "name": prov.get("name", ""),
                        "entity_type": etype,
                        "field": field,
                        "reason": f"Required field '{field}' missing on {etype} entity",
                    }
                )
    return issues


def _get_builtin_spec(source_name: str) -> dict | None:
    """Get built-in validation spec for a known source."""
    specs = {
        "bids": _bids_spec(),
        "dandi": _dandi_spec(),
        "nwb": _nwb_spec(),
        "openminds": _openminds_spec(),
        "aind": _aind_spec(),
    }
    return specs.get(source_name)


def _bids_spec() -> dict:
    """Validation spec for BIDS extraction."""
    return {
        "expected_types": {
            "attribute": {"min": 400, "max": 600},  # metadata fields
            "enum_value": {"min": 200, "max": 500},  # enum entries + vocabulary terms
            "valueset": {"min": 5, "max": 30},  # underscore valuesets
            "class": {"min": 5, "max": 20},  # structural classes (not vocabulary categories)
        },
        "category_rules": {
            # These categories contain vocabulary terms, not data elements
            "enums": "enum_value",
            "datatypes": "enum_value",
            "modalities": "enum_value",
            "suffixes": "enum_value",
            "extensions": "enum_value",
            # These contain actual data elements
            "metadata": "attribute",
            "columns": "attribute",
        },
        "known_entities": [
            {"name": "age", "class": "columns", "type": "attribute"},
            {"name": "sex", "class": "columns", "type": "attribute"},
            {"name": "RepetitionTime", "class": "metadata", "type": "attribute"},
            {"name": "TaskName", "class": "metadata", "type": "attribute"},
            {"name": "CASL", "class": "enums", "type": "enum_value"},
            {"name": "left_hemisphere", "class": "enums", "type": "enum_value"},
            {"name": "T1w", "class": "suffixes", "type": "enum_value"},
            {"name": "bold", "class": "suffixes", "type": "enum_value"},
            {"name": "anat", "class": "datatypes", "type": "enum_value"},
        ],
        "required_fields": {
            "attribute": ["data_type"],
            "enum_value": ["label"],
        },
    }


def _dandi_spec() -> dict:
    return {
        "expected_types": {
            "attribute": {"min": 200, "max": 500},
            "enum_value": {"min": 80, "max": 200},
            "valueset": {"min": 10, "max": 40},
            "class": {"min": 20, "max": 50},
        },
        "known_entities": [
            {"name": "name", "class": "Dandiset", "type": "attribute"},
            {"name": "description", "class": "Dandiset", "type": "attribute"},
            {"name": "Person", "class": "", "type": "class"},
            {"name": "Organization", "class": "", "type": "class"},
        ],
        "required_fields": {
            "attribute": ["data_type"],
            "enum_value": ["label"],
        },
    }


def _nwb_spec() -> dict:
    return {
        "expected_types": {
            "attribute": {"min": 200, "max": 500},
            "class": {"min": 50, "max": 150},
        },
        "known_entities": [
            {"name": "TimeSeries", "type": "class"},
            {"name": "NWBFile", "type": "class"},
            {"name": "ElectricalSeries", "type": "class"},
        ],
        "required_fields": {
            "attribute": ["data_type"],
        },
    }


def _openminds_spec() -> dict:
    return {
        "expected_types": {
            "attribute": {"min": 2000, "max": 6000},
            "valueset": {"min": 50, "max": 150},
            "class": {"min": 100, "max": 400},
        },
        "known_entities": [
            {"name": "Person", "type": "class"},
            {"name": "BiologicalSex", "type": "valueset"},
            {"name": "Species", "type": "valueset"},
        ],
        "required_fields": {
            "attribute": ["data_type"],
        },
    }


def _aind_spec() -> dict:
    return {
        "expected_types": {
            "attribute": {"min": 800, "max": 2000},
            "enum_value": {"min": 200, "max": 800},
            "valueset": {"min": 30, "max": 100},
            "class": {"min": 50, "max": 200},
        },
        "known_entities": [
            {"name": "Subject", "type": "class"},
            {"name": "Sex", "type": "valueset"},
        ],
        "required_fields": {
            "attribute": ["data_type"],
            "enum_value": ["label"],
        },
    }


def print_validation_report(report: dict) -> None:
    """Print a human-readable validation report."""
    print(f"\n{'=' * 60}")
    print(f"Extraction Validation: {report['source']}")
    print(f"{'=' * 60}")
    print(f"Total entities: {report['total_entities']}")
    print(f"Quality score: {report['score']:.1%}")
    print("\nEntity counts:")
    for etype, count in sorted(report["entity_counts"].items()):
        print(f"  {etype}: {count}")

    if report["classification_issues"]:
        print(f"\nClassification issues ({len(report['classification_issues'])}):")
        # Group by category
        by_cat = {}
        for issue in report["classification_issues"]:
            cat = issue.get("category", "other")
            by_cat.setdefault(cat, []).append(issue)
        for cat, issues in sorted(by_cat.items()):
            print(
                f"  {cat}: {len(issues)} entities (expected {issues[0]['expected_type']}, got {issues[0]['actual_type']})"
            )

    if report["missing_entities"]:
        print(f"\nMissing entities ({len(report['missing_entities'])}):")
        for me in report["missing_entities"][:10]:
            print(f"  {me['reason']}")

    if report["field_issues"]:
        # Summarize by field
        field_counts = Counter(fi["field"] for fi in report["field_issues"])
        print(f"\nMissing semantic fields ({len(report['field_issues'])}):")
        for field, count in field_counts.most_common():
            print(f"  {field}: {count} entities missing")

    print(f"\n{'=' * 60}\n")
