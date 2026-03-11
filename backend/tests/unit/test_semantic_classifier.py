"""Unit tests for SemanticChangeClassifier — ValidationRule breaking-change detection.

TDD: These tests MUST FAIL before src/services/validation_rule.py is implemented.
Covers all 6 rule types per FR-006.
"""

from __future__ import annotations

import pytest


class TestSemanticChangeClassifier:
    """Tests for the pure classify(rule_type, old_value, new_value) -> bool function."""

    # --- enum_set ---

    def test_enum_set_narrowing_is_breaking(self):
        from src.services.validation_rule import classify

        old = {"values": ["M", "F", "O"]}
        new = {"values": ["M", "F"]}
        assert classify("enum_set", old, new) is True

    def test_enum_set_widening_is_not_breaking(self):
        from src.services.validation_rule import classify

        old = {"values": ["M", "F"]}
        new = {"values": ["M", "F", "O"]}
        assert classify("enum_set", old, new) is False

    def test_enum_set_same_values_is_not_breaking(self):
        from src.services.validation_rule import classify

        old = {"values": ["M", "F", "O"]}
        new = {"values": ["M", "F", "O"]}
        assert classify("enum_set", old, new) is False

    def test_enum_set_replace_one_value_is_breaking(self):
        """Replacing 'O' with 'X' removes 'O' from the set — breaking."""
        from src.services.validation_rule import classify

        old = {"values": ["M", "F", "O"]}
        new = {"values": ["M", "F", "X"]}
        assert classify("enum_set", old, new) is True

    # --- range ---

    def test_range_tighten_max_is_breaking(self):
        from src.services.validation_rule import classify

        old = {"min": 0, "max": 120}
        new = {"min": 0, "max": 100}
        assert classify("range", old, new) is True

    def test_range_raise_min_is_breaking(self):
        from src.services.validation_rule import classify

        old = {"min": 0, "max": 120}
        new = {"min": 18, "max": 120}
        assert classify("range", old, new) is True

    def test_range_widen_max_is_not_breaking(self):
        from src.services.validation_rule import classify

        old = {"min": 0, "max": 120}
        new = {"min": 0, "max": 150}
        assert classify("range", old, new) is False

    def test_range_lower_min_is_not_breaking(self):
        from src.services.validation_rule import classify

        old = {"min": 18, "max": 120}
        new = {"min": 0, "max": 120}
        assert classify("range", old, new) is False

    def test_range_only_max_no_min_change(self):
        from src.services.validation_rule import classify

        old = {"max": 100}
        new = {"max": 50}
        assert classify("range", old, new) is True

    # --- pattern ---

    def test_pattern_add_regex_is_breaking(self):
        """Adding a new regex constraint = narrowing."""
        from src.services.validation_rule import classify

        old = {}
        new = {"regex": "^[A-Z]{2}[0-9]{3}$"}
        assert classify("pattern", old, new) is True

    def test_pattern_remove_regex_is_not_breaking(self):
        """Removing a regex constraint = widening."""
        from src.services.validation_rule import classify

        old = {"regex": "^[A-Z]{2}[0-9]{3}$"}
        new = {}
        assert classify("pattern", old, new) is False

    def test_pattern_change_regex_is_breaking(self):
        """Changing from one regex to another = adding new constraint."""
        from src.services.validation_rule import classify

        old = {"regex": "^[A-Z]+$"}
        new = {"regex": "^[A-Z]{2}[0-9]{3}$"}
        assert classify("pattern", old, new) is True

    # --- type_constraint ---

    def test_type_constraint_change_is_always_breaking(self):
        from src.services.validation_rule import classify

        old = {"type": "string"}
        new = {"type": "integer"}
        assert classify("type_constraint", old, new) is True

    def test_type_constraint_same_type_is_not_breaking(self):
        from src.services.validation_rule import classify

        old = {"type": "string"}
        new = {"type": "string"}
        assert classify("type_constraint", old, new) is False

    # --- cardinality ---

    def test_cardinality_increase_min_is_breaking(self):
        from src.services.validation_rule import classify

        old = {"min_count": 0, "max_count": 5}
        new = {"min_count": 1, "max_count": 5}
        assert classify("cardinality", old, new) is True

    def test_cardinality_decrease_max_is_breaking(self):
        from src.services.validation_rule import classify

        old = {"min_count": 0, "max_count": 5}
        new = {"min_count": 0, "max_count": 3}
        assert classify("cardinality", old, new) is True

    def test_cardinality_decrease_min_is_not_breaking(self):
        from src.services.validation_rule import classify

        old = {"min_count": 1, "max_count": 5}
        new = {"min_count": 0, "max_count": 5}
        assert classify("cardinality", old, new) is False

    def test_cardinality_increase_max_is_not_breaking(self):
        from src.services.validation_rule import classify

        old = {"min_count": 0, "max_count": 5}
        new = {"min_count": 0, "max_count": 10}
        assert classify("cardinality", old, new) is False

    # --- unknown rule_type ---

    def test_unknown_rule_type_returns_false(self):
        from src.services.validation_rule import classify

        assert classify("unknown_type", {}, {}) is False
