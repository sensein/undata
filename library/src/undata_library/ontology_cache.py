"""Offline ontology term cache for alignment verification."""

from __future__ import annotations

from pathlib import Path

import yaml


class OntologyCache:
    """Manages a local cache of ontology terms for offline verification."""

    def __init__(self, cache_dir: Path):
        self.cache_dir = cache_dir
        self._loaded: dict[str, dict] = {}

    def load(self, ontology_name: str) -> dict:
        """Load an ontology cache file. Returns {term_uri: {label, synonyms, parents, deprecated}}."""
        if ontology_name in self._loaded:
            return self._loaded[ontology_name]

        path = self.cache_dir / f"{ontology_name.lower()}.yaml"
        if not path.exists():
            return {}

        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        terms = data.get("terms", {}) if isinstance(data, dict) else {}
        self._loaded[ontology_name] = terms
        return terms

    def load_all(self) -> dict[str, dict]:
        """Load all cached ontologies. Returns flat {term_uri: {label, ...}} merged dict."""
        merged: dict[str, dict] = {}
        for f in self.cache_dir.glob("*.yaml"):
            name = f.stem
            terms = self.load(name)
            merged.update(terms)
        return merged

    def lookup(self, term_uri: str) -> dict | None:
        """Look up a term URI across all loaded ontologies."""
        all_terms = self.load_all()
        return all_terms.get(term_uri)

    def save(self, ontology_name: str, data: dict) -> None:
        """Save ontology cache file."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        path = self.cache_dir / f"{ontology_name.lower()}.yaml"
        path.write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
