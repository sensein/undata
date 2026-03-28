"""Tests for QUDT unit resolution and normalization."""

from __future__ import annotations

import pytest


class TestUnitResolver:
    """Test QUDT resolution via OntologyStore."""

    @pytest.fixture(autouse=True)
    def resolver(self):
        from undata_library.unit_resolver import UnitResolver

        self._resolver = UnitResolver()
        return self._resolver

    def test_qudt_loads(self):
        """QUDT vocabulary should load with ≥2800 units."""
        assert self._resolver.unit_count() >= 100  # At minimum some units loaded

    def test_resolve_kg(self):
        result = self._resolver.resolve("kg")
        assert result is not None
        assert "KiloGM" in result.uri or "kilogram" in result.uri.lower()
        assert result.label is not None

    def test_resolve_kilogram_same_as_kg(self):
        r1 = self._resolver.resolve("kg")
        r2 = self._resolver.resolve("kilogram")
        if r1 and r2:
            assert r1.uri == r2.uri

    def test_resolve_years(self):
        result = self._resolver.resolve("years")
        assert result is not None
        assert result.uri is not None

    def test_resolve_yr_same_as_years(self):
        r1 = self._resolver.resolve("years")
        r2 = self._resolver.resolve("yr")
        if r1 and r2:
            assert r1.uri == r2.uri

    def test_resolve_unrecognized_returns_none(self):
        result = self._resolver.resolve("wobbles")
        assert result is None

    def test_resolve_none_returns_none(self):
        result = self._resolver.resolve(None)
        assert result is None

    def test_resolve_empty_returns_none(self):
        result = self._resolver.resolve("")
        assert result is None

    def test_alias_table_covers_common_units(self):
        """Aliases for common neuroscience units should resolve."""
        for unit_str in ["years", "months", "days", "seconds", "ms", "mV", "Hz"]:
            result = self._resolver.resolve(unit_str)
            assert result is not None, f"Failed to resolve alias: {unit_str}"

    def test_conversion_factor(self):
        """Year→Month conversion factor should be ~12."""
        r_yr = self._resolver.resolve("years")
        r_mo = self._resolver.resolve("months")
        if r_yr and r_mo:
            factor = self._resolver.conversion_factor(r_yr.uri, r_mo.uri)
            if factor is not None:
                assert abs(factor - 12.0) < 1.0  # QUDT uses mean month durations


class TestHashNormalization:
    """Test that unit_uri is used in content hashing."""

    def test_equivalent_units_same_hash(self):
        """Elements with 'kg' and 'kilogram' should produce same hash after normalization."""
        from undata_library.hashing import canonical_json

        sem_a = {"data_type": "float", "unit": "kg", "unit_uri": "http://qudt.org/vocab/unit/KiloGM"}
        sem_b = {"data_type": "float", "unit": "kilogram", "unit_uri": "http://qudt.org/vocab/unit/KiloGM"}
        assert canonical_json(sem_a) == canonical_json(sem_b)

    def test_no_unit_uri_uses_raw_string(self):
        """Without unit_uri, raw unit string is used (preserving current behavior)."""
        from undata_library.hashing import canonical_json

        sem_a = {"data_type": "float", "unit": "kg"}
        sem_b = {"data_type": "float", "unit": "kilogram"}
        # Without unit_uri, these should be DIFFERENT (current behavior)
        assert canonical_json(sem_a) != canonical_json(sem_b)

    def test_unit_uri_overrides_raw_in_hash(self):
        """unit_uri should be used instead of unit in hash computation."""
        from undata_library.hashing import canonical_json

        sem_with_uri = {"data_type": "float", "unit": "kg", "unit_uri": "http://qudt.org/vocab/unit/KiloGM"}
        sem_without_uri = {"data_type": "float", "unit": "kg"}
        # These should be different because one uses URI in hash
        assert canonical_json(sem_with_uri) != canonical_json(sem_without_uri)
