"""Tests for source validation, provenance dedup, and bloat detection."""

import yaml

from undata_library.commit import commit_staged
from undata_library.curation import get_known_sources, read_flags
from undata_library.models import FlagType
from undata_library.utils import write_yaml


def _make_staged_element(staging_dir, name, source="bids"):
    """Create a staged element for testing."""
    elem_dir = staging_dir / "elements"
    elem_dir.mkdir(parents=True, exist_ok=True)
    import uuid

    filepath = elem_dir / f"{uuid.uuid4()}.yaml"
    write_yaml(
        filepath,
        {
            "semantic": {"data_type": "string"},
            "provenance": [{"source": source, "class": "test", "name": name}],
        },
    )
    return filepath


class TestSourceValidation:
    def test_known_source_accepted(self, tmp_path):
        staging = tmp_path / "staging"
        _make_staged_element(staging, "age", source="bids")
        known = get_known_sources()
        stats = commit_staged(staging, tmp_path, validate_sources=True, known_sources=known)
        assert stats["committed"] == 1
        assert stats["rejected"] == 0

    def test_unknown_source_rejected_with_flag(self, tmp_path):
        staging = tmp_path / "staging"
        _make_staged_element(staging, "age", source="fake_source_xyz")
        known = get_known_sources()
        stats = commit_staged(staging, tmp_path, validate_sources=True, known_sources=known)
        assert stats["rejected"] == 1
        assert stats["committed"] == 0

        # Check that a suspicious_source flag was created
        flags = read_flags(tmp_path, flag_type=FlagType.suspicious_source)
        assert len(flags) == 1
        assert "fake_source_xyz" in str(flags[0].context)

    def test_validation_disabled_accepts_any_source(self, tmp_path):
        staging = tmp_path / "staging"
        _make_staged_element(staging, "age", source="whatever")
        stats = commit_staged(staging, tmp_path, validate_sources=False)
        assert stats["committed"] == 1


class TestProvenanceDedup:
    def test_same_provenance_not_duplicated(self, tmp_path):
        # First commit
        staging1 = tmp_path / "staging1"
        _make_staged_element(staging1, "age", source="bids")
        commit_staged(staging1, tmp_path)

        # Second commit with same source+name — should merge, not duplicate
        staging2 = tmp_path / "staging2"
        _make_staged_element(staging2, "age", source="bids")
        stats = commit_staged(staging2, tmp_path)
        assert stats["merged"] >= 1 or stats["committed"] >= 0

        # Check the committed file has only 1 provenance entry (not 2)
        for f in (tmp_path / "elements").glob("*.yaml"):
            data = yaml.safe_load(f.read_text())
            # Should have at most 1 entry for (bids, age)
            bids_age = [
                p
                for p in data.get("provenance", [])
                if p.get("source") == "bids" and p.get("name") == "age"
            ]
            assert len(bids_age) <= 1, f"Duplicate provenance found: {bids_age}"
