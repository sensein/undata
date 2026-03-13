"""Unit tests for roundtrip functions — must FAIL before implementation (TDD)."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from undata.roundtrip import RoundtripResult, roundtrip_json_schema, roundtrip_linkml

JSON_FIXTURE = Path(__file__).parent.parent / "fixtures" / "generic_schema_sample.json"
LINKML_FIXTURE = Path(__file__).parent.parent / "fixtures" / "linkml_sample.yaml"


# ── RoundtripResult dataclass ─────────────────────────────────────────────────


def test_roundtrip_result_is_dataclass():
    r = RoundtripResult(
        fidelity_score=1.0,
        missing_classes=[],
        missing_elements=[],
        warnings=[],
    )
    assert r.fidelity_score == 1.0
    assert r.missing_classes == []
    assert r.missing_elements == []
    assert r.warnings == []


def test_roundtrip_result_partial_loss():
    r = RoundtripResult(
        fidelity_score=0.5,
        missing_classes=["Foo"],
        missing_elements=["bar"],
        warnings=["cycle detected"],
    )
    assert r.fidelity_score == 0.5
    assert "Foo" in r.missing_classes
    assert "bar" in r.missing_elements


# ── roundtrip_json_schema ─────────────────────────────────────────────────────


def test_roundtrip_json_schema_returns_result():
    result = roundtrip_json_schema(str(JSON_FIXTURE))
    assert isinstance(result, RoundtripResult)


def test_roundtrip_json_schema_fidelity_in_range():
    result = roundtrip_json_schema(str(JSON_FIXTURE))
    assert 0.0 <= result.fidelity_score <= 1.0


def test_roundtrip_json_schema_lists_are_sorted():
    result = roundtrip_json_schema(str(JSON_FIXTURE))
    assert result.missing_elements == sorted(result.missing_elements)
    assert result.missing_classes == sorted(result.missing_classes)


def test_roundtrip_json_schema_good_fidelity():
    """Sample fixture has simple types — expect high fidelity (>= 0.5)."""
    result = roundtrip_json_schema(str(JSON_FIXTURE))
    assert result.fidelity_score >= 0.5, (
        f"Unexpectedly low fidelity: {result.fidelity_score}; "
        f"missing_elements={result.missing_elements}, "
        f"missing_classes={result.missing_classes}"
    )


def test_roundtrip_json_schema_empty_schema():
    with tempfile.NamedTemporaryFile(suffix=".json", mode="w", delete=False) as f:
        json.dump({}, f)
        tmp_path = f.name
    result = roundtrip_json_schema(tmp_path)
    assert result.fidelity_score == 1.0
    assert result.missing_elements == []
    assert result.missing_classes == []


def test_roundtrip_json_schema_empty_path_raises():
    with pytest.raises(ValueError):
        roundtrip_json_schema("")


def test_roundtrip_json_schema_nonexistent_raises():
    with pytest.raises((FileNotFoundError, OSError)):
        roundtrip_json_schema("/nonexistent/does_not_exist.json")


# ── roundtrip_linkml ──────────────────────────────────────────────────────────


def test_roundtrip_linkml_returns_result():
    result = roundtrip_linkml(str(LINKML_FIXTURE))
    assert isinstance(result, RoundtripResult)


def test_roundtrip_linkml_fidelity_in_range():
    result = roundtrip_linkml(str(LINKML_FIXTURE))
    assert 0.0 <= result.fidelity_score <= 1.0


def test_roundtrip_linkml_high_fidelity():
    """Simple LinkML fixture should survive a dump+reload with perfect fidelity."""
    result = roundtrip_linkml(str(LINKML_FIXTURE))
    assert result.fidelity_score >= 0.8, (
        f"Unexpectedly low fidelity: {result.fidelity_score}; "
        f"missing_elements={result.missing_elements}, "
        f"missing_classes={result.missing_classes}"
    )


def test_roundtrip_linkml_lists_are_sorted():
    result = roundtrip_linkml(str(LINKML_FIXTURE))
    assert result.missing_elements == sorted(result.missing_elements)
    assert result.missing_classes == sorted(result.missing_classes)


def test_roundtrip_linkml_empty_path_raises():
    with pytest.raises(ValueError):
        roundtrip_linkml("")


def test_roundtrip_linkml_nonexistent_raises():
    with pytest.raises((FileNotFoundError, OSError, Exception)):
        roundtrip_linkml("/nonexistent/does_not_exist.yaml")
