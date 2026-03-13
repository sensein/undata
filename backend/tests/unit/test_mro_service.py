"""Unit tests for MROService — C3 linearization, cycle detection, depth check.

TDD: These tests MUST FAIL before src/services/schema_mro.py is implemented.
"""

from __future__ import annotations

import pytest


class TestC3Linearize:
    """Tests for the pure c3_merge function."""

    def test_simple_single_inheritance(self):
        """A → B gives [A, B]."""
        from src.services.schema_mro import c3_merge

        result = c3_merge([["A"], ["B"], ["B"]])
        assert result == ["A", "B"]

    def test_linear_chain(self):
        """A → B → C gives [A, B, C]."""
        from src.services.schema_mro import c3_merge

        result = c3_merge([["A"], ["B", "C"], ["C"], ["B"], ["C"]])
        assert result == ["A", "B", "C"]

    def test_diamond_inheritance(self):
        """A → B, A → C, B → D, C → D gives [A, B, C, D]."""
        from src.services.schema_mro import c3_merge

        # A inherits B and C; both B and C inherit D
        # Sequences: [A], [B,D], [C,D], [B,C]
        result = c3_merge([["A"], ["B", "D"], ["C", "D"], ["B", "C"]])
        assert result == ["A", "B", "C", "D"]

    def test_mixin_precedence_by_position(self):
        """Earlier mixins have higher precedence (appear earlier in MRO)."""
        from src.services.schema_mro import c3_merge

        # Schema A with mixin B (pos 0) and mixin C (pos 1)
        result = c3_merge([["A"], ["B"], ["C"], ["B", "C"]])
        assert result == ["A", "B", "C"]

    def test_no_parents_returns_self(self):
        from src.services.schema_mro import c3_merge

        result = c3_merge([["A"]])
        assert result == ["A"]

    def test_inconsistent_hierarchy_raises_cycle_error(self):
        from src.services.schema_mro import CycleError, c3_merge

        # Impossible: A→B and B→A in sequences
        with pytest.raises(CycleError):
            c3_merge([["A", "B"], ["B", "A"]])


class TestCycleDetection:
    """Tests for detect_cycle — validates no circular inheritance."""

    def test_no_cycle_in_simple_chain(self):
        """A → B → C: setting C's parent to A creates a 3-level chain (ok)."""
        from src.services.schema_mro import detect_cycle_in_adjacency

        # adjacency: {id: parent_id or None}
        graph = {"A": None, "B": "A", "C": "B"}
        # Adding D with parent C: no cycle
        assert detect_cycle_in_adjacency(graph, proposed_id="D", proposed_parent="C") is False

    def test_direct_cycle_detected(self):
        """A → B: setting A's parent to B would create A → B → A."""
        from src.services.schema_mro import detect_cycle_in_adjacency

        graph = {"A": None, "B": "A"}
        assert detect_cycle_in_adjacency(graph, proposed_id="A", proposed_parent="B") is True

    def test_indirect_cycle_detected(self):
        """A → B → C: setting A's parent to C creates cycle A → B → C → A."""
        from src.services.schema_mro import detect_cycle_in_adjacency

        graph = {"A": None, "B": "A", "C": "B"}
        assert detect_cycle_in_adjacency(graph, proposed_id="A", proposed_parent="C") is True

    def test_self_cycle_detected(self):
        """Setting a schema's parent to itself."""
        from src.services.schema_mro import detect_cycle_in_adjacency

        graph = {"A": None}
        assert detect_cycle_in_adjacency(graph, proposed_id="A", proposed_parent="A") is True


class TestDepthCheck:
    """Tests for check_depth — max 20 levels enforced."""

    def test_depth_exceeding_max_raises(self):
        from src.services.schema_mro import DepthError, check_depth_limit

        with pytest.raises(DepthError):
            check_depth_limit(21)

    def test_depth_at_max_is_ok(self):
        from src.services.schema_mro import check_depth_limit

        check_depth_limit(20)  # Should not raise

    def test_depth_zero_is_ok(self):
        from src.services.schema_mro import check_depth_limit

        check_depth_limit(0)


class TestMROElementDeduplication:
    """Tests for element deduplication by source_local_id (own schema wins)."""

    def test_own_element_overrides_parent(self):
        """When child and parent define same source_local_id, child wins."""
        from src.services.schema_mro import deduplicate_elements_by_source_local_id

        child_elems = [{"source_local_id": "age", "name": "Age (child)", "source_schema": "Child"}]
        parent_elems = [{"source_local_id": "age", "name": "Age (parent)", "source_schema": "Parent"}]
        result = deduplicate_elements_by_source_local_id(child_elems + parent_elems)
        # First occurrence (child) wins
        assert len(result) == 1
        assert result[0]["name"] == "Age (child)"

    def test_no_duplicates_returned_unchanged(self):
        from src.services.schema_mro import deduplicate_elements_by_source_local_id

        elems = [
            {"source_local_id": "age", "name": "Age", "source_schema": "A"},
            {"source_local_id": "sex", "name": "Sex", "source_schema": "A"},
        ]
        result = deduplicate_elements_by_source_local_id(elems)
        assert len(result) == 2


class TestMRONameCollisionWarning:
    """Tests for mixin element-name collision warning (T065)."""

    def test_collision_warning_emitted(self, caplog):
        """When two schemas in MRO define the same source_local_id, a WARNING is logged."""
        import logging

        from src.services.schema_mro import deduplicate_elements_by_source_local_id

        elems = [
            {"source_local_id": "age", "name": "Age", "source_schema": "SchemaA", "source_schema_id": "id-a"},
            {"source_local_id": "age", "name": "Age", "source_schema": "SchemaB", "source_schema_id": "id-b"},
        ]
        with caplog.at_level(logging.WARNING, logger="src.services.schema_mro"):
            deduplicate_elements_by_source_local_id(elems)

        assert any("collision" in rec.message.lower() or "override" in rec.message.lower()
                   for rec in caplog.records)
