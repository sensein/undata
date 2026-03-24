"""Tests for source discovery and candidate approval workflow."""

from undata_library.discovery import (
    approve_candidate,
    load_candidates,
    reject_candidate,
    save_candidates,
)


class TestCandidatePersistence:
    def test_save_and_load_roundtrip(self, tmp_path):
        candidates = [
            {
                "name": "test-ontology",
                "url": "http://example.org/test.owl",
                "format": "owl",
                "registry": "obo_foundry",
                "relevance_score": 0.8,
                "description": "A test ontology",
                "discovered_at": "2026-03-22T00:00:00Z",
                "status": "pending",
            }
        ]
        save_candidates(tmp_path, candidates)
        loaded = load_candidates(tmp_path)
        assert len(loaded) == 1
        assert loaded[0]["name"] == "test-ontology"

    def test_save_merges_with_existing(self, tmp_path):
        c1 = [{"name": "a", "url": "http://a.org", "status": "pending"}]
        c2 = [{"name": "b", "url": "http://b.org", "status": "pending"}]
        save_candidates(tmp_path, c1)
        save_candidates(tmp_path, c2)
        loaded = load_candidates(tmp_path)
        assert len(loaded) == 2

    def test_save_deduplicates_by_url(self, tmp_path):
        c1 = [{"name": "a", "url": "http://a.org", "status": "pending"}]
        save_candidates(tmp_path, c1)
        save_candidates(tmp_path, c1)  # same URL
        loaded = load_candidates(tmp_path)
        assert len(loaded) == 1

    def test_load_empty(self, tmp_path):
        assert load_candidates(tmp_path) == []


class TestApproveReject:
    def test_approve_candidate(self, tmp_path):
        candidates = [{"name": "x", "url": "http://x.org", "status": "pending"}]
        save_candidates(tmp_path, candidates)
        result = approve_candidate(tmp_path, "http://x.org", "curator1")
        assert result is True
        loaded = load_candidates(tmp_path)
        assert loaded[0]["status"] == "approved"
        assert loaded[0]["approved_by"] == "curator1"

    def test_reject_candidate(self, tmp_path):
        candidates = [{"name": "x", "url": "http://x.org", "status": "pending"}]
        save_candidates(tmp_path, candidates)
        result = reject_candidate(tmp_path, "http://x.org", "curator1", "not relevant")
        assert result is True
        loaded = load_candidates(tmp_path)
        assert loaded[0]["status"] == "rejected"
        assert loaded[0]["rejection_reason"] == "not relevant"

    def test_approve_nonexistent(self, tmp_path):
        candidates = [{"name": "x", "url": "http://x.org", "status": "pending"}]
        save_candidates(tmp_path, candidates)
        result = approve_candidate(tmp_path, "http://nonexistent.org", "curator1")
        assert result is False

    def test_approve_empty_dir(self, tmp_path):
        result = approve_candidate(tmp_path, "http://x.org", "curator1")
        assert result is False
