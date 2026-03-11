"""Unit tests for CycleDetector — T049.

Pure Python tests, no DB, no FastAPI.
Tests MUST FAIL before T053 (cycle_detection.py) is implemented.
"""

from __future__ import annotations

import pytest


class TestCycleDetectorDFS:
    def test_no_cycle_returns_none(self):
        """A valid DAG (A→B, B→C) returns None."""
        from src.services.cycle_detection import CycleDetector

        adjacency = [("A", "B"), ("B", "C")]
        result = CycleDetector.detect_cycle_dfs(adjacency, ["D"], "E")
        assert result is None

    def test_direct_cycle_detected(self):
        """Direct A↔B cycle is detected."""
        from src.services.cycle_detection import CycleDetector

        # Existing: A→B, propose B→A
        adjacency = [("A", "B")]
        result = CycleDetector.detect_cycle_dfs(adjacency, ["B"], "A")
        assert result is not None
        assert "A" in result or "B" in result

    def test_transitive_cycle_detected(self):
        """Transitive cycle A→B→C→A is detected."""
        from src.services.cycle_detection import CycleDetector

        adjacency = [("A", "B"), ("B", "C")]
        result = CycleDetector.detect_cycle_dfs(adjacency, ["C"], "A")
        assert result is not None

    def test_self_loop_detected(self):
        """Self-loop (A→A) is detected."""
        from src.services.cycle_detection import CycleDetector

        adjacency = []
        result = CycleDetector.detect_cycle_dfs(adjacency, ["A"], "A")
        assert result is not None

    def test_valid_deep_dag_returns_none(self):
        """A complex valid DAG (A→B, A→C, B→D, C→D) returns None."""
        from src.services.cycle_detection import CycleDetector

        adjacency = [("A", "B"), ("A", "C"), ("B", "D"), ("C", "D")]
        # Propose E→F (new leaf)
        result = CycleDetector.detect_cycle_dfs(adjacency, ["E"], "F")
        assert result is None

    def test_cycle_path_is_returned(self):
        """When cycle detected, a non-empty path is returned."""
        from src.services.cycle_detection import CycleDetector

        adjacency = [("X", "Y"), ("Y", "Z")]
        result = CycleDetector.detect_cycle_dfs(adjacency, ["Z"], "X")
        assert result is not None
        assert isinstance(result, list)
        assert len(result) >= 2
