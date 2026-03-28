"""Tests for OntologyStore (pyoxigraph-backed RDF store)."""

from pathlib import Path

from undata_library.ontology_store import OntologyStore, load_ontology_config

_MINI_OBO = """\
format-version: 1.4
ontology: test

[Term]
id: TEST:0001
name: Age
synonym: "patient age" EXACT []
is_a: TEST:0000 ! Root

[Term]
id: TEST:0002
name: Species
synonym: "organism species" EXACT []
is_a: TEST:0000 ! Root

[Term]
id: TEST:0003
name: Deprecated Term
is_obsolete: true

[Term]
id: TEST:0000
name: Root
"""


def _write_obo(tmp_path: Path) -> Path:
    obo = tmp_path / "test.obo"
    obo.write_text(_MINI_OBO)
    return obo


def test_store_creates_directory(tmp_path):
    store_path = tmp_path / "store"
    OntologyStore(store_path)
    assert store_path.exists()


def test_load_obo_term_count(tmp_path):
    store = OntologyStore(tmp_path / "store")
    obo = _write_obo(tmp_path)
    count = store.load_obo("test", obo)
    assert count == 4  # 4 [Term] stanzas


def test_lookup_term(tmp_path):
    store = OntologyStore(tmp_path / "store")
    obo = _write_obo(tmp_path)
    store.load_obo("test", obo)

    result = store.lookup_term("http://purl.obolibrary.org/obo/TEST_0001")
    assert result is not None
    assert result["label"] == "Age"
    assert "patient age" in result["synonyms"]
    assert any("TEST_0000" in p for p in result["parents"])
    assert result["deprecated"] is False


def test_lookup_unknown_returns_none(tmp_path):
    store = OntologyStore(tmp_path / "store")
    assert store.lookup_term("http://example.org/nonexistent") is None


def test_search_terms(tmp_path):
    store = OntologyStore(tmp_path / "store")
    store.load_obo("test", _write_obo(tmp_path))

    results = store.search_terms("age")
    assert len(results) >= 1
    assert any(r["label"] == "Age" for r in results)


def test_term_count(tmp_path):
    store = OntologyStore(tmp_path / "store")
    store.load_obo("test", _write_obo(tmp_path))
    assert store.term_count("test") >= 3  # 3 non-obsolete + 1 obsolete with label


def test_list_loaded(tmp_path):
    store = OntologyStore(tmp_path / "store")
    store.load_obo("test", _write_obo(tmp_path))
    loaded = store.list_loaded()
    assert len(loaded) == 1
    assert loaded[0]["name"] == "test"
    assert loaded[0]["term_count"] >= 3


def test_store_persists(tmp_path):
    store_path = tmp_path / "store"
    store1 = OntologyStore(store_path)
    store1.load_obo("test", _write_obo(tmp_path))
    count1 = store1.term_count()
    del store1

    store2 = OntologyStore(store_path)
    count2 = store2.term_count()
    assert count2 == count1  # Persisted across instantiations


def test_load_ontology_config():
    configs = load_ontology_config()
    names = {c["name"] for c in configs}
    assert {"ncit", "pato", "hp", "obi", "ncbitaxon"}.issubset(names)
    assert len(names) >= 10  # 5 original + UBERON, CL, EDAM, SKOS, PROV-O
    for c in configs:
        assert c["url"].startswith("http") or c["url"] == "bundled"
        assert c["format"] in ("obo", "owl", "ttl", "custom")
