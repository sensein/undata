"""Test pipeline functions with MockBackend to verify file system decoupling.

These tests verify that pipeline functions interact with the StorageBackend
protocol methods rather than directly touching the file system.
"""

from __future__ import annotations


from undata_library.curation import create_flag, read_flags, resolve_flag, write_flag
from undata_library.models import FlagStatus, FlagType
from undata_library.run_summary import (
    generate_summary,
    load_previous_summary,
    save_summary,
)
from undata_library.storage import MockBackend


class TestCurationWithBackend:
    """Test curation functions delegate to FlagStore."""

    def test_write_flag_uses_backend(self):
        backend = MockBackend()
        flag = create_flag("element", "age_abc", FlagType.low_confidence, {"score": 0.4})
        write_flag(None, flag, backend=backend)
        assert len(backend.flags.operations) >= 1
        assert any(op[0] == "write_flag" for op in backend.flags.operations)

    def test_read_flags_uses_backend(self):
        backend = MockBackend()
        flag = create_flag("element", "age_abc", FlagType.low_confidence, {"score": 0.4})
        backend.flags.write_flag(flag)
        flags = read_flags(None, backend=backend)
        assert len(flags) == 1

    def test_resolve_flag_uses_backend(self):
        backend = MockBackend()
        flag = create_flag("element", "age_abc", FlagType.low_confidence, {"score": 0.4})
        flag_id = backend.flags.write_flag(flag)
        result = resolve_flag(None, flag_id, FlagStatus.approved, "curator", backend=backend)
        assert result is not None
        assert result.status == FlagStatus.approved


class TestRunSummaryWithBackend:
    """Test run summary functions delegate to RunStore."""

    def test_save_summary_uses_backend(self):
        backend = MockBackend()
        summary = generate_summary("run-1", "bids", {"extract": {"elements": 100}})
        save_summary(None, summary, backend=backend)
        assert len(backend.runs.operations) >= 1
        assert any(op[0] == "save_summary" for op in backend.runs.operations)

    def test_load_previous_uses_backend(self):
        backend = MockBackend()
        summary = generate_summary("run-1", "bids", {"extract": {"elements": 100}})
        backend.runs.save_summary(summary)
        result = load_previous_summary(None, "bids", backend=backend)
        assert result is not None
        assert result.source == "bids"
