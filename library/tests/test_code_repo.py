"""Tests for Docker-based code inspection adapter."""

from undata_library.adapters.code_repo import CodeRepoAdapter


def test_detect_language_python(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'")
    adapter = CodeRepoAdapter()
    assert adapter._detect_language(tmp_path) == "python"


def test_detect_language_typescript(tmp_path):
    (tmp_path / "package.json").write_text('{"name": "test"}')
    adapter = CodeRepoAdapter()
    assert adapter._detect_language(tmp_path) == "typescript"


def test_detect_language_tsconfig(tmp_path):
    (tmp_path / "tsconfig.json").write_text("{}")
    adapter = CodeRepoAdapter()
    assert adapter._detect_language(tmp_path) == "typescript"


def test_detect_language_unknown(tmp_path):
    adapter = CodeRepoAdapter()
    assert adapter._detect_language(tmp_path) is None


def test_json_output_parsing():
    """Verify JSON output from container is parsed into ClassifiedEntity."""
    mock_output = [
        {
            "entity_type": "class",
            "semantic": {"properties": ["name", "age"]},
            "provenance": {"source": "test-pkg", "class": "Subject", "name": "Subject"},
            "confidence": 0.9,
            "source_context": {"module": "test_pkg.models"},
        },
        {
            "entity_type": "attribute",
            "semantic": {"data_type": "string"},
            "provenance": {"source": "test-pkg", "class": "Subject", "name": "name"},
            "confidence": 0.85,
            "source_context": {"module": "test_pkg.models"},
        },
    ]

    from undata_library.models import EntityType, SourceRef

    results = []
    for item in mock_output:
        etype = EntityType(item["entity_type"])
        ref = SourceRef(repo=None, committish=None, file="test", checksum="")
        from undata_library.adapters.base import ClassifiedEntity

        results.append(
            ClassifiedEntity(
                entity_type=etype,
                semantic=item["semantic"],
                provenance=item["provenance"],
                confidence=item["confidence"],
                source_ref=ref,
            )
        )

    assert len(results) == 2
    assert results[0].entity_type == EntityType.CLASS
    assert results[1].entity_type == EntityType.ATTRIBUTE


def test_fallback_on_no_language(tmp_path):
    """Unknown language → empty results (no crash)."""
    adapter = CodeRepoAdapter()
    results = adapter.extract(tmp_path)
    assert results == []
