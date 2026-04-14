"""Tests for the alignment pipeline (Feature 041)."""

import json

from undata_library.align import (
    _designate_canonical,
    _form_groups,
    _has_alignment,
    _intra_source_dedup,
    _ranges_compatible,
    align_entities,
)
from undata_library.similarity import compute_alignment_score, normalize_name


# -- normalize_name tests --


def test_normalize_name_basic():
    assert normalize_name("participant_id") == "participantid"
    assert normalize_name("interview_age") == "interviewage"
    assert normalize_name("ParticipantID") == "participantid"


def test_normalize_name_strips_separators():
    assert normalize_name("roi-name") == "roiname"
    assert normalize_name("roi name") == "roiname"
    assert normalize_name("roi_name") == "roiname"


def test_normalize_name_unicode():
    assert normalize_name("café") == "cafe"


# -- range compatibility tests --


def test_ranges_compatible_both_absent():
    a = {"semantic": {}}
    b = {"semantic": {}}
    assert _ranges_compatible(a, b) is True


def test_ranges_compatible_one_absent():
    a = {"semantic": {"min_value": 0, "max_value": 100}}
    b = {"semantic": {}}
    assert _ranges_compatible(a, b) is True


def test_ranges_compatible_same():
    a = {"semantic": {"min_value": 0, "max_value": 100}}
    b = {"semantic": {"min_value": 0, "max_value": 100}}
    assert _ranges_compatible(a, b) is True


def test_ranges_incompatible():
    a = {"semantic": {"min_value": 0, "max_value": 100}}
    b = {"semantic": {"min_value": 18, "max_value": 65}}
    assert _ranges_compatible(a, b) is False


# -- has_alignment tests --


def test_has_alignment_none():
    assert _has_alignment({"semantic": {}}) is False


def test_has_alignment_aligned_to():
    assert _has_alignment({"semantic": {"aligned_to": "abc123"}}) is True


def test_has_alignment_aligned_members():
    assert _has_alignment({"semantic": {"aligned_members": ["a", "b"]}}) is True


def test_has_alignment_json_string():
    assert _has_alignment({"semantic": json.dumps({"aligned_to": "abc"})}) is True


# -- intra-source dedup tests --


def test_intra_source_dedup_same_name_type():
    entities = [
        {
            "sha256": "aaa",
            "semantic": {"data_type": "integer"},
            "provenance": [{"source": "openneuro/ds001", "name": "age"}],
        },
        {
            "sha256": "bbb",
            "semantic": {"data_type": "integer"},
            "provenance": [{"source": "openneuro/ds002", "name": "age"}],
        },
    ]
    # Same source prefix doesn't match — these are different sources
    groups = _intra_source_dedup(entities)
    assert len(groups) == 0  # Different sources → no intra-source group


def test_intra_source_dedup_same_source():
    entities = [
        {
            "sha256": "aaa",
            "semantic": {"data_type": "integer"},
            "provenance": [{"source": "bids", "name": "age"}],
        },
        {
            "sha256": "bbb",
            "semantic": {"data_type": "integer"},
            "provenance": [{"source": "bids", "name": "age"}],
        },
    ]
    groups = _intra_source_dedup(entities)
    assert len(groups) == 1
    assert set(groups[0]) == {"aaa", "bbb"}


def test_intra_source_dedup_different_types():
    entities = [
        {
            "sha256": "aaa",
            "semantic": {"data_type": "integer"},
            "provenance": [{"source": "bids", "name": "age"}],
        },
        {
            "sha256": "bbb",
            "semantic": {"data_type": "string"},
            "provenance": [{"source": "bids", "name": "age"}],
        },
    ]
    groups = _intra_source_dedup(entities)
    assert len(groups) == 0  # Different types → separate


# -- group formation tests --


def test_form_groups_basic():
    pairs = [("a", "b", 0.9), ("b", "c", 0.85)]
    by_sha = {
        "a": {"semantic": {}},
        "b": {"semantic": {}},
        "c": {"semantic": {}},
    }
    groups, conflicts = _form_groups(pairs, by_sha)
    assert len(groups) == 1
    assert set(groups[0]) == {"a", "b", "c"}
    assert conflicts == 0


def test_form_groups_range_conflict():
    pairs = [("a", "b", 0.9)]
    by_sha = {
        "a": {"semantic": {"min_value": 0, "max_value": 100}},
        "b": {"semantic": {"min_value": 18, "max_value": 65}},
    }
    groups, conflicts = _form_groups(pairs, by_sha)
    assert len(groups) == 0
    assert conflicts == 1


def test_form_groups_empty():
    groups, conflicts = _form_groups([], {})
    assert groups == []
    assert conflicts == 0


# -- canonical designation tests --


def test_designate_canonical_earliest():
    group = ["sha_b", "sha_a", "sha_c"]
    by_sha = {
        "sha_a": {"created_at": "2026-01-01T00:00:00"},
        "sha_b": {"created_at": "2026-01-02T00:00:00"},
        "sha_c": {"created_at": "2026-01-03T00:00:00"},
    }
    canonical, members = _designate_canonical(group, by_sha)
    assert canonical == "sha_a"
    assert set(members) == {"sha_b", "sha_c"}


# -- alignment scoring tests --


def test_compute_alignment_score_identical_names():
    a = {"provenance": [{"source": "bids", "name": "age"}], "semantic": {}}
    b = {"provenance": [{"source": "nda", "name": "age"}], "semantic": {}}
    score = compute_alignment_score(a, b)
    assert score["name"] == 1.0
    assert score["composite"] > 0.0


def test_compute_alignment_score_different_names():
    a = {"provenance": [{"source": "bids", "name": "age"}], "semantic": {}}
    b = {"provenance": [{"source": "nda", "name": "sex"}], "semantic": {}}
    score = compute_alignment_score(a, b)
    assert score["name"] < 0.5


def test_compute_alignment_score_alias_boost():
    a = {
        "provenance": [{"source": "nda", "name": "sex"}],
        "semantic": {"alias_hints": ["nda_alias:gender"]},
    }
    b = {
        "provenance": [{"source": "bids", "name": "gender"}],
        "semantic": {"alias_hints": ["nda_alias:gender"]},
    }
    score = compute_alignment_score(a, b)
    assert score["alias"] == 0.95


# -- integration test --


def test_align_entities_empty(tmp_path):
    """Alignment on empty registry returns zero stats."""
    stats = align_entities(registry_path=tmp_path)
    assert stats["total_entities_processed"] == 0
    assert stats["alignment_groups"] == 0


def test_align_entities_dry_run(tmp_path):
    """Dry run doesn't write alignment report."""
    stats = align_entities(registry_path=tmp_path, dry_run=True)
    assert not (tmp_path / "alignment-report.yaml").exists()
