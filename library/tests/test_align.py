"""Tests for the alignment pipeline."""

import yaml

from undata_library.align import (
    _build_report,
    _compute_diff,
    _form_alias_groups,
    align_elements,
)


# -- union-find grouping tests --


def test_form_alias_groups_exact_match():
    candidates = [
        {
            "element_a": "a.yaml",
            "element_b": "b.yaml",
            "score": 0.96,
            "relation": "skos:exactMatch",
            "components": {},
        },
        {
            "element_a": "b.yaml",
            "element_b": "c.yaml",
            "score": 0.97,
            "relation": "skos:exactMatch",
            "components": {},
        },
    ]
    exact, close = _form_alias_groups(candidates)
    assert len(exact) == 1
    assert set(exact[0]) == {"a.yaml", "b.yaml", "c.yaml"}
    assert len(close) == 0


def test_form_alias_groups_close_match():
    candidates = [
        {
            "element_a": "a.yaml",
            "element_b": "b.yaml",
            "score": 0.85,
            "relation": "skos:closeMatch",
            "components": {},
        },
    ]
    exact, close = _form_alias_groups(candidates)
    assert len(exact) == 0
    assert len(close) == 1
    assert set(close[0]) == {"a.yaml", "b.yaml"}


def test_form_alias_groups_mixed():
    candidates = [
        {
            "element_a": "a.yaml",
            "element_b": "b.yaml",
            "score": 0.96,
            "relation": "skos:exactMatch",
            "components": {},
        },
        {
            "element_a": "c.yaml",
            "element_b": "d.yaml",
            "score": 0.85,
            "relation": "skos:closeMatch",
            "components": {},
        },
    ]
    exact, close = _form_alias_groups(candidates)
    assert len(exact) == 1
    assert len(close) == 1


def test_form_alias_groups_no_candidates():
    exact, close = _form_alias_groups([])
    assert exact == []
    assert close == []


# -- diff tests --


def test_compute_diff_no_previous():
    diff = _compute_diff([["a", "b"]], [["c", "d"]], None)
    assert diff["new_groups"] == 2
    assert diff["unchanged_groups"] == 0
    assert diff["dissolved_groups"] == 0


def test_compute_diff_with_previous():
    prev = {
        "groups": [
            {"members": ["a", "b"], "relation": "skos:exactMatch"},
            {"members": ["e", "f"], "relation": "skos:closeMatch"},
        ]
    }
    diff = _compute_diff([["a", "b"]], [["c", "d"]], prev)
    assert diff["unchanged_groups"] == 1  # [a, b] still exists
    assert diff["new_groups"] == 1  # [c, d] is new
    assert diff["dissolved_groups"] == 1  # [e, f] dissolved


# -- report building tests --


def test_build_report_structure():
    candidates = [
        {
            "element_a": "a.yaml",
            "element_b": "b.yaml",
            "score": 0.96,
            "relation": "skos:exactMatch",
            "components": {},
        },
    ]
    report = _build_report(
        [["a.yaml", "b.yaml"]],
        [],
        candidates,
        {"new_groups": 1, "unchanged_groups": 0, "dissolved_groups": 0},
    )
    assert "generated_at" in report
    assert report["stats"]["exact_match_groups"] == 1
    assert len(report["groups"]) == 1
    assert report["groups"][0]["relation"] == "skos:exactMatch"


# -- integration tests --


def _make_elements(tmp_path, elements):
    """Create element YAML files."""
    elem_dir = tmp_path / "elements"
    elem_dir.mkdir(exist_ok=True)
    for name, data in elements.items():
        (elem_dir / name).write_text(yaml.dump(data, default_flow_style=False))
    return elem_dir


def test_align_elements_basic(tmp_path):
    """Elements with same data_type get compared."""
    elements = {
        "age_a.yaml": {
            "semantic": {"data_type": "string", "ontology_term": "http://example.org/age"},
            "provenance": [{"source": "bids", "name": "age"}],
        },
        "age_b.yaml": {
            "semantic": {"data_type": "string", "ontology_term": "http://example.org/age"},
            "provenance": [{"source": "nwb", "name": "age"}],
        },
    }
    elem_dir = _make_elements(tmp_path, elements)

    stats = align_elements(
        elements_dir=elem_dir,
        library_path=tmp_path,
        threshold=0.3,
    )

    assert stats["total_pairs_evaluated"] >= 1
    # Report should be written
    report_path = tmp_path / "alignment-report.yaml"
    assert report_path.exists()
    report = yaml.safe_load(report_path.read_text())
    assert "groups" in report


def test_align_dry_run(tmp_path):
    elements = {
        "x_a.yaml": {
            "semantic": {"data_type": "string"},
            "provenance": [{"source": "a", "name": "x"}],
        },
    }
    _make_elements(tmp_path, elements)

    align_elements(
        elements_dir=tmp_path / "elements",
        library_path=tmp_path,
        dry_run=True,
    )

    assert not (tmp_path / "alignment-report.yaml").exists()


def test_align_idempotent(tmp_path):
    """Second run with same data produces no new groups."""
    elements = {
        "a.yaml": {
            "semantic": {"data_type": "string"},
            "provenance": [{"source": "test", "name": "field_a"}],
        },
    }
    _make_elements(tmp_path, elements)

    # First run
    align_elements(elements_dir=tmp_path / "elements", library_path=tmp_path)
    # Second run
    stats = align_elements(elements_dir=tmp_path / "elements", library_path=tmp_path)

    assert stats["new_groups"] == 0
