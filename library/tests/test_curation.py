"""Tests for curation flag management."""

from undata_library.curation import (
    create_flag,
    get_known_sources,
    read_flags,
    resolve_flag,
    write_flag,
)
from undata_library.models import FlagStatus, FlagType


class TestCreateFlag:
    def test_creates_with_uuid_and_timestamp(self):
        flag = create_flag(
            entity_type="element",
            entity_ref="age_abc123.yaml",
            flag_type=FlagType.low_confidence,
            context={"reason": "score 0.65"},
        )
        assert len(flag.id) == 36  # UUID format
        assert flag.status == FlagStatus.pending
        assert flag.created_at is not None

    def test_creates_with_llm_verification(self):
        flag = create_flag(
            entity_type="value",
            entity_ref="male_xyz.yaml",
            flag_type=FlagType.ambiguous_match,
            context={"candidates": [{"uri": "http://x", "score": 0.85}]},
            llm_verification={"model": "claude-haiku", "response": "reject"},
        )
        assert flag.llm_verification is not None
        assert flag.llm_verification["model"] == "claude-haiku"


class TestWriteReadFlags:
    def test_write_and_read_roundtrip(self, tmp_path):
        flag = create_flag(
            entity_type="element",
            entity_ref="test.yaml",
            flag_type=FlagType.needs_review,
            context={"reason": "test"},
        )
        write_flag(tmp_path, flag)

        flags = read_flags(tmp_path)
        assert len(flags) == 1
        assert flags[0].id == flag.id
        assert flags[0].flag_type == FlagType.needs_review

    def test_filter_by_status(self, tmp_path):
        f1 = create_flag("element", "a.yaml", FlagType.low_confidence, {})
        f2 = create_flag("element", "b.yaml", FlagType.low_confidence, {})
        write_flag(tmp_path, f1)
        write_flag(tmp_path, f2)

        # Resolve one
        resolve_flag(tmp_path, f1.id, FlagStatus.approved, "curator1")

        pending = read_flags(tmp_path, status=FlagStatus.pending)
        assert len(pending) == 1
        assert pending[0].id == f2.id

    def test_filter_by_type(self, tmp_path):
        f1 = create_flag("element", "a.yaml", FlagType.low_confidence, {})
        f2 = create_flag("transform", "b.yaml", FlagType.unknown_transform, {})
        write_flag(tmp_path, f1)
        write_flag(tmp_path, f2)

        transforms = read_flags(tmp_path, flag_type=FlagType.unknown_transform)
        assert len(transforms) == 1
        assert transforms[0].flag_type == FlagType.unknown_transform

    def test_empty_directory(self, tmp_path):
        assert read_flags(tmp_path) == []


class TestResolveFlag:
    def test_approve_flag(self, tmp_path):
        flag = create_flag("element", "test.yaml", FlagType.low_confidence, {})
        write_flag(tmp_path, flag)

        result = resolve_flag(tmp_path, flag.id, FlagStatus.approved, "curator1", "looks good")
        assert result is not None
        assert result.status == FlagStatus.approved
        assert result.resolved_by == "curator1"
        assert result.resolution_note == "looks good"
        assert result.resolved_at is not None

    def test_reject_flag(self, tmp_path):
        flag = create_flag("element", "test.yaml", FlagType.ambiguous_match, {})
        write_flag(tmp_path, flag)

        result = resolve_flag(tmp_path, flag.id, FlagStatus.rejected, "curator2")
        assert result is not None
        assert result.status == FlagStatus.rejected

    def test_resolve_nonexistent(self, tmp_path):
        result = resolve_flag(tmp_path, "nonexistent-id", FlagStatus.approved, "curator")
        assert result is None


class TestGetKnownSources:
    def test_reads_source_defs(self, tmp_path):
        from undata_library.utils import write_yaml

        write_yaml(tmp_path / "bids.yaml", {"name": "bids", "adapter": "bids"})
        write_yaml(tmp_path / "dandi.yaml", {"name": "dandi", "adapter": "dandi"})
        write_yaml(tmp_path / "ontologies.yaml", {"ontologies": []})  # should be skipped

        sources = get_known_sources(tmp_path)
        assert sources == {"bids", "dandi"}

    def test_fallback_to_stem(self, tmp_path):
        from undata_library.utils import write_yaml

        write_yaml(tmp_path / "custom.yaml", {"adapter": "json_schema"})  # no "name" key
        sources = get_known_sources(tmp_path)
        assert "custom" in sources

    def test_empty_directory(self, tmp_path):
        assert get_known_sources(tmp_path) == set()

    def test_bundled_sources(self):
        """The bundled source_defs should return at least 5 known sources."""
        sources = get_known_sources()
        assert len(sources) >= 5
        assert "bids" in sources
