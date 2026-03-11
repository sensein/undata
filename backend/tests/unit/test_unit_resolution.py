"""Unit tests for UnitResolutionService — T094.

Tests MUST FAIL before T097 (UnitResolutionService) is implemented.
"""

from __future__ import annotations

import os

import pytest

# TTL path relative to the backend/ working directory
TTL_PATH = os.path.join(os.path.dirname(__file__), "../../data/qudt/VOCAB_QUDT-UNITS-ALL.ttl")


@pytest.fixture(scope="module")
def unit_service():
    """Load UnitResolutionService once for the test module."""
    from src.services.units import UnitResolutionService

    return UnitResolutionService(ttl_path=TTL_PATH)


class TestUnitResolutionService:
    def test_kilogram_resolves(self, unit_service):
        """kg is a standard SI unit — must resolve to QUDT URI."""
        result = unit_service.resolve(label="kilogram", symbol="kg")
        assert result.qudt_uri is not None, "kilogram should resolve to a QUDT URI"
        assert "qudt.org/vocab/unit" in result.qudt_uri
        assert result.cmixf_valid is True, "kg is valid cmixf symbol"
        assert result.qudt_unresolvable is False

    def test_year_resolves_via_label(self, unit_service):
        """'a' is the UCUM code for year; label fallback should also work."""
        result = unit_service.resolve(label="year", symbol="a")
        # QUDT has YR / year; may resolve via label or ucum code
        assert result.qudt_unresolvable is False or result.qudt_uri is not None
        assert result.cmixf_valid is not None  # symbol provided → bool result

    def test_degree_celsius_via_symbol_override(self, unit_service):
        """ASCII 'oC' is in SYMBOL_OVERRIDES → maps to QUDT DEG_C URI."""
        result = unit_service.resolve(label="degree Celsius", symbol="oC")
        assert result.qudt_uri is not None, "oC should resolve via SYMBOL_OVERRIDES"
        assert "DEG_C" in result.qudt_uri or "celsius" in result.qudt_uri.lower()
        assert result.qudt_unresolvable is False

    def test_unknown_unit_is_unresolvable(self, unit_service):
        """Completely made-up unit should not resolve."""
        result = unit_service.resolve(label="unknown_unit_xyz_123", symbol="???_invalid")
        assert result.qudt_unresolvable is True
        assert result.qudt_uri is None
        assert result.cmixf_valid is False  # invalid cmixf symbol

    def test_no_symbol_or_label_returns_null_cmixf(self, unit_service):
        """No symbol → cmixf_valid=None; no label → qudt_unresolvable=False (not attempted)."""
        result = unit_service.resolve(label=None, symbol=None)
        assert result.cmixf_valid is None
        assert result.qudt_unresolvable is False
        assert result.qudt_uri is None

    def test_list_known_returns_many_units(self, unit_service):
        """list_known() should return > 2000 units from the bundled TTL."""
        units = unit_service.list_known()
        assert len(units) > 2000, f"Expected > 2000 units, got {len(units)}"
        # Each item must have expected keys
        sample = units[0]
        assert "label" in sample
        assert "qudt_uri" in sample

    def test_metre_resolves(self, unit_service):
        """m (metre) is a canonical SI unit."""
        result = unit_service.resolve(label="metre", symbol="m")
        assert result.qudt_uri is not None
        assert result.cmixf_valid is True

    def test_symbol_none_label_known(self, unit_service):
        """When symbol=None, cmixf_valid must be None; QUDT lookup via label only."""
        result = unit_service.resolve(label="kilogram", symbol=None)
        assert result.cmixf_valid is None  # no symbol → not validated
        assert result.qudt_uri is not None  # label 'kilogram' should resolve
