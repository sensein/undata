"""Tests for run summary generation and delta comparison."""

from undata_library.run_summary import (
    compute_delta,
    compute_entity_delta,
    generate_summary,
    load_previous_summary,
    save_summary,
)
from undata_library.utils import write_yaml


class TestGenerateSummary:
    def test_creates_summary(self):
        summary = generate_summary(
            run_id="test-run-001",
            source="bids",
            entity_counts={"elements": 100, "schemas": 10},
        )
        assert summary.run_id == "test-run-001"
        assert summary.source == "bids"
        assert summary.entity_counts["elements"] == 100
        assert summary.started_at is not None

    def test_with_all_fields(self):
        summary = generate_summary(
            run_id="test-run-002",
            source="dandi",
            entity_counts={"elements": 50},
            enrichment_rate={"ontology_assigned": 10},
            curation_flags={"low_confidence": 5},
            timing={"extract_s": 1.5},
        )
        assert summary.enrichment_rate is not None
        assert summary.curation_flags["low_confidence"] == 5


class TestSaveLoadSummary:
    def test_save_and_load_roundtrip(self, tmp_path):
        summary = generate_summary(
            run_id="rt-001",
            source="bids",
            entity_counts={"elements": 100},
        )
        save_summary(tmp_path, summary)

        loaded = load_previous_summary(tmp_path, "bids")
        assert loaded is not None
        assert loaded.run_id == "rt-001"
        assert loaded.entity_counts["elements"] == 100

    def test_load_latest_of_multiple(self, tmp_path):
        s1 = generate_summary("run-1", "bids", {"elements": 50})
        s1.started_at = "2026-03-01T00:00:00"
        save_summary(tmp_path, s1)

        s2 = generate_summary("run-2", "bids", {"elements": 100})
        s2.started_at = "2026-03-02T00:00:00"
        save_summary(tmp_path, s2)

        loaded = load_previous_summary(tmp_path, "bids")
        assert loaded is not None
        assert loaded.run_id == "run-2"

    def test_load_no_previous(self, tmp_path):
        assert load_previous_summary(tmp_path, "bids") is None

    def test_load_wrong_source(self, tmp_path):
        summary = generate_summary("run-1", "bids", {"elements": 50})
        save_summary(tmp_path, summary)
        assert load_previous_summary(tmp_path, "dandi") is None


class TestComputeDelta:
    def test_no_changes(self):
        delta = compute_delta({"elements": 100}, {"elements": 100})
        assert delta["elements"] == {"added": 0, "removed": 0}

    def test_additions(self):
        delta = compute_delta({"elements": 110}, {"elements": 100})
        assert delta["elements"] == {"added": 10, "removed": 0}

    def test_removals(self):
        delta = compute_delta({"elements": 90}, {"elements": 100})
        assert delta["elements"] == {"added": 0, "removed": 10}

    def test_new_entity_type(self):
        delta = compute_delta({"elements": 100, "values": 50}, {"elements": 100})
        assert delta["values"] == {"added": 50, "removed": 0}

    def test_removed_entity_type(self):
        delta = compute_delta({"elements": 100}, {"elements": 100, "values": 50})
        assert delta["values"] == {"added": 0, "removed": 50}


class TestComputeEntityDelta:
    def test_no_changes(self, tmp_path):
        d = tmp_path / "elements"
        d.mkdir()
        write_yaml(d / "a.yaml", {"sha256": "abc123", "semantic": {}})
        write_yaml(d / "b.yaml", {"sha256": "def456", "semantic": {}})

        delta = compute_entity_delta(d, {"a.yaml": "abc123", "b.yaml": "def456"})
        assert delta["added"] == []
        assert delta["removed"] == []
        assert delta["modified"] == []

    def test_added_entity(self, tmp_path):
        d = tmp_path / "elements"
        d.mkdir()
        write_yaml(d / "a.yaml", {"sha256": "abc123", "semantic": {}})
        write_yaml(d / "b.yaml", {"sha256": "def456", "semantic": {}})

        delta = compute_entity_delta(d, {"a.yaml": "abc123"})
        assert delta["added"] == ["b.yaml"]

    def test_removed_entity(self, tmp_path):
        d = tmp_path / "elements"
        d.mkdir()
        write_yaml(d / "a.yaml", {"sha256": "abc123", "semantic": {}})

        delta = compute_entity_delta(d, {"a.yaml": "abc123", "b.yaml": "def456"})
        assert delta["removed"] == ["b.yaml"]

    def test_modified_entity(self, tmp_path):
        d = tmp_path / "elements"
        d.mkdir()
        write_yaml(d / "a.yaml", {"sha256": "new_hash", "semantic": {}})

        delta = compute_entity_delta(d, {"a.yaml": "old_hash"})
        assert delta["modified"] == ["a.yaml"]
