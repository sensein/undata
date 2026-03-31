"""Tests for OpenNeuro adapter — extract elements from TSV/CSV with JSON sidecars."""

from __future__ import annotations

import json
from pathlib import Path

from undata_library.adapters.openneuro import OpenNeuroAdapter


def _create_mock_dataset(tmp_path: Path) -> Path:
    """Create a minimal mock BIDS dataset structure."""
    ds = tmp_path / "ds000001"
    ds.mkdir()

    # participants.tsv
    (ds / "participants.tsv").write_text(
        "participant_id\tage\tsex\thandedness\n"
        "sub-01\t25\tM\tR\n"
        "sub-02\t30\tF\tL\n"
        "sub-03\t28\tM\tR\n",
        encoding="utf-8",
    )

    # participants.json (sidecar)
    (ds / "participants.json").write_text(
        json.dumps({
            "age": {"Description": "Age of participant in years", "Units": "years"},
            "sex": {"Description": "Biological sex", "Levels": {"M": "male", "F": "female"}},
            "handedness": {"Description": "Handedness", "Levels": {"R": "right", "L": "left"}},
        }),
        encoding="utf-8",
    )

    # phenotype directory
    pheno = ds / "phenotype"
    pheno.mkdir()
    (pheno / "iq.tsv").write_text(
        "participant_id\tiq_score\tiq_type\n"
        "sub-01\t115\tWASI\n"
        "sub-02\t120\tWASI\n",
        encoding="utf-8",
    )

    return ds


def test_extract_participants_tsv(tmp_path):
    ds = _create_mock_dataset(tmp_path)
    adapter = OpenNeuroAdapter()
    entities = adapter.extract(ds)

    names = [e.provenance["name"] for e in entities]
    assert "age" in names
    assert "sex" in names
    assert "handedness" in names
    assert "participant_id" in names


def test_infer_types_from_values(tmp_path):
    ds = _create_mock_dataset(tmp_path)
    adapter = OpenNeuroAdapter()
    entities = adapter.extract(ds)

    by_name = {e.provenance["name"]: e for e in entities}
    assert by_name["age"].semantic["data_type"] == "integer"
    assert by_name["sex"].semantic["data_type"] == "string"


def test_json_sidecar_description(tmp_path):
    ds = _create_mock_dataset(tmp_path)
    adapter = OpenNeuroAdapter()
    entities = adapter.extract(ds)

    by_name = {e.provenance["name"]: e for e in entities}
    assert by_name["age"].provenance["description"] == "Age of participant in years"


def test_json_sidecar_unit(tmp_path):
    ds = _create_mock_dataset(tmp_path)
    adapter = OpenNeuroAdapter()
    entities = adapter.extract(ds)

    by_name = {e.provenance["name"]: e for e in entities}
    assert by_name["age"].semantic.get("unit") == "years"


def test_json_sidecar_response_options(tmp_path):
    ds = _create_mock_dataset(tmp_path)
    adapter = OpenNeuroAdapter()
    entities = adapter.extract(ds)

    by_name = {e.provenance["name"]: e for e in entities}
    sex = by_name["sex"]
    opts = sex.semantic.get("response_options", [])
    assert len(opts) == 2
    vals = {o["value"] for o in opts}
    assert "M" in vals
    assert "F" in vals


def test_phenotype_tsv_extraction(tmp_path):
    ds = _create_mock_dataset(tmp_path)
    adapter = OpenNeuroAdapter()
    entities = adapter.extract(ds)

    names = [e.provenance["name"] for e in entities]
    assert "iq_score" in names
    assert "iq_type" in names


def test_source_provenance(tmp_path):
    ds = _create_mock_dataset(tmp_path)
    adapter = OpenNeuroAdapter()
    entities = adapter.extract(ds)

    for e in entities:
        assert e.provenance["source"].startswith("openneuro/")
