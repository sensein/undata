"""Local ontology service — persistent pyoxigraph RDF store with SPARQL queries."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

import pyoxigraph
import yaml

logger = logging.getLogger(__name__)

_RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
_RDFS_SUBCLASS = "http://www.w3.org/2000/01/rdf-schema#subClassOf"
_OWL_DEPRECATED = "http://www.w3.org/2002/07/owl#deprecated"
_OBO_SYNONYM = "http://www.geneontology.org/formats/oboInOwl#hasExactSynonym"
_OBO_NAMESPACE = "http://www.geneontology.org/formats/oboInOwl#hasOBONamespace"
_UNDATA_LOADED = "http://schema.undata.live/ontology-meta/loaded"
_UNDATA_LOADED_AT = "http://schema.undata.live/ontology-meta/loadedAt"

_BUNDLED_CONFIG = Path(__file__).parent / "source_defs" / "ontologies.yaml"


def _val(node) -> str:
    """Extract string value from pyoxigraph Literal or NamedNode."""
    if hasattr(node, "value"):
        return node.value
    return str(node)


def _obo_id_to_uri(obo_id: str) -> str:
    """Convert OBO ID (NCIT:C25150) to full URI."""
    if obo_id.startswith("http"):
        return obo_id
    if ":" in obo_id:
        prefix, local = obo_id.split(":", 1)
        return f"http://purl.obolibrary.org/obo/{prefix}_{local}"
    return obo_id


class OntologyStore:
    """Persistent RDF store for ontology terms using pyoxigraph."""

    def __init__(self, store_path: Path):
        store_path.mkdir(parents=True, exist_ok=True)
        self.store_path = store_path
        self.store = pyoxigraph.Store(str(store_path))

    def load_obo(self, name: str, obo_path: Path) -> int:
        """Parse OBO file via fast line parser and insert RDF triples. Returns term count."""
        logger.info("Loading %s from %s into store", name, obo_path)
        graph = pyoxigraph.NamedNode(f"http://schema.undata.live/ontology/{name}")
        count = 0
        current_id: str | None = None
        in_term = False

        with open(obo_path, encoding="utf-8", errors="replace") as f:
            for line in f:
                line = line.rstrip("\n")

                if line == "[Term]":
                    in_term = True
                    current_id = None
                    continue
                if line.startswith("[") and line.endswith("]"):
                    in_term = False
                    current_id = None
                    continue
                if not in_term:
                    continue

                if line.startswith("id: "):
                    current_id = _obo_id_to_uri(line[4:].strip())
                    count += 1
                elif current_id and line.startswith("name: "):
                    self._add_triple(current_id, _RDFS_LABEL, line[6:].strip(), graph)
                elif current_id and line.startswith("synonym: "):
                    m = re.match(r'^synonym:\s+"([^"]*)"', line)
                    if m:
                        self._add_triple(current_id, _OBO_SYNONYM, m.group(1), graph)
                elif current_id and line.startswith("is_a: "):
                    parent = _obo_id_to_uri(line[6:].strip().split("!")[0].strip())
                    self._add_triple_uri(current_id, _RDFS_SUBCLASS, parent, graph)
                elif current_id and line.startswith("is_obsolete: true"):
                    self._add_triple(current_id, _OWL_DEPRECATED, "true", graph)
                elif current_id and line.startswith("namespace: "):
                    self._add_triple(current_id, _OBO_NAMESPACE, line[11:].strip(), graph)

        # Record metadata
        now = datetime.now(timezone.utc).isoformat()
        meta_graph = pyoxigraph.NamedNode("http://schema.undata.live/ontology-meta")
        self._add_triple(
            f"http://schema.undata.live/ontology/{name}", _UNDATA_LOADED, "true", meta_graph
        )
        self._add_triple(
            f"http://schema.undata.live/ontology/{name}", _UNDATA_LOADED_AT, now, meta_graph
        )

        logger.info("Loaded %s: %d terms", name, count)
        return count

    def load_rdf(self, name: str, rdf_path: Path, fmt: str = "application/rdf+xml") -> int:
        """Load OWL/TTL/RDF-XML directly via pyoxigraph."""
        graph = pyoxigraph.NamedNode(f"http://schema.undata.live/ontology/{name}")
        mime = {"owl": "application/rdf+xml", "ttl": "text/turtle", "nt": "application/n-triples"}
        content_type = mime.get(fmt, fmt)
        self.store.load(rdf_path.read_bytes(), content_type, to_graph=graph)
        # Count terms (subjects with rdfs:label)
        results = self.store.query(
            f"SELECT (COUNT(DISTINCT ?s) AS ?c) FROM <{graph.value}> "
            f"WHERE {{ ?s <{_RDFS_LABEL}> ?l }}"
        )
        count = 0
        for row in results:
            count = int(_val(row[0]))
        return count

    def lookup_term(self, uri: str) -> dict | None:
        """SPARQL lookup for a single term: label, synonyms, parents, deprecated."""
        label_q = f"SELECT ?l WHERE {{ GRAPH ?g {{ <{uri}> <{_RDFS_LABEL}> ?l }} }} LIMIT 1"
        label = None
        for row in self.store.query(label_q):
            label = _val(row[0])
        if label is None:
            return None

        syn_q = f"SELECT ?s WHERE {{ GRAPH ?g {{ <{uri}> <{_OBO_SYNONYM}> ?s }} }}"
        synonyms = [_val(row[0]) for row in self.store.query(syn_q)]

        par_q = f"SELECT ?p WHERE {{ GRAPH ?g {{ <{uri}> <{_RDFS_SUBCLASS}> ?p }} }}"
        parents = [_val(row[0]) for row in self.store.query(par_q)]

        dep_q = f"SELECT ?d WHERE {{ GRAPH ?g {{ <{uri}> <{_OWL_DEPRECATED}> ?d }} }} LIMIT 1"
        deprecated = False
        for row in self.store.query(dep_q):
            deprecated = _val(row[0]).lower() == "true"

        return {
            "label": label,
            "synonyms": synonyms,
            "parents": parents,
            "deprecated": deprecated,
        }

    def search_terms(self, query: str, ontology: str | None = None, limit: int = 100) -> list[dict]:
        """Search terms by label or synonym substring match."""
        q_lower = query.lower().replace('"', '\\"')

        if ontology:
            sparql = (
                f"SELECT DISTINCT ?s ?l WHERE {{ "
                f"GRAPH <http://schema.undata.live/ontology/{ontology}> {{ "
                f'?s <{_RDFS_LABEL}> ?l . FILTER(CONTAINS(LCASE(STR(?l)), "{q_lower}")) '
                f"}} }} LIMIT {limit}"
            )
        else:
            sparql = (
                f"SELECT DISTINCT ?s ?l WHERE {{ GRAPH ?g {{ "
                f'?s <{_RDFS_LABEL}> ?l . FILTER(CONTAINS(LCASE(STR(?l)), "{q_lower}")) '
                f"}} }} LIMIT {limit}"
            )

        results = []
        for row in self.store.query(sparql):
            results.append({"uri": _val(row[0]), "label": _val(row[1])})
        return results

    def all_terms(self) -> Iterator[tuple[str, str, list[str]]]:
        """Yield (uri, label, synonyms) for all non-deprecated terms with labels."""
        sparql = (
            f"SELECT ?s ?l WHERE {{ GRAPH ?g {{ "
            f"?s <{_RDFS_LABEL}> ?l . "
            f'FILTER NOT EXISTS {{ ?s <{_OWL_DEPRECATED}> "true" }} '
            f"}} }}"
        )
        # Batch: collect URIs first, then fetch synonyms
        terms: dict[str, str] = {}
        for row in self.store.query(sparql):
            uri = _val(row[0])
            label = _val(row[1])
            terms[uri] = label

        for uri, label in terms.items():
            syn_q = f"SELECT ?s WHERE {{ GRAPH ?g {{ <{uri}> <{_OBO_SYNONYM}> ?s }} }}"
            synonyms = [_val(row[0]) for row in self.store.query(syn_q)]
            yield uri, label, synonyms

    def term_count(self, ontology: str | None = None) -> int:
        """Count terms in store."""
        if ontology:
            graph = f"http://schema.undata.live/ontology/{ontology}"
            sparql = f"SELECT (COUNT(DISTINCT ?s) AS ?c) FROM <{graph}> WHERE {{ ?s <{_RDFS_LABEL}> ?l }}"
        else:
            sparql = f"SELECT (COUNT(DISTINCT ?s) AS ?c) WHERE {{ GRAPH ?g {{ ?s <{_RDFS_LABEL}> ?l }} }}"
        for row in self.store.query(sparql):
            return int(_val(row[0]))
        return 0

    def list_loaded(self) -> list[dict]:
        """List loaded ontologies with metadata."""
        sparql = (
            f"SELECT ?ont ?loaded_at WHERE {{ "
            f"GRAPH <http://schema.undata.live/ontology-meta> {{ "
            f'?ont <{_UNDATA_LOADED}> "true" . '
            f"OPTIONAL {{ ?ont <{_UNDATA_LOADED_AT}> ?loaded_at }} "
            f"}} }}"
        )
        results = []
        for row in self.store.query(sparql):
            ont_uri = _val(row[0])
            name = ont_uri.rsplit("/", 1)[-1]
            loaded_at = _val(row[1]) if row[1] else None
            count = self.term_count(name)
            results.append({"name": name, "term_count": count, "loaded_at": loaded_at})
        return results

    def _add_triple(
        self,
        subject: str,
        predicate: str,
        obj_literal: str,
        graph: pyoxigraph.NamedNode,
    ) -> None:
        self.store.add(
            pyoxigraph.Quad(
                pyoxigraph.NamedNode(subject),
                pyoxigraph.NamedNode(predicate),
                pyoxigraph.Literal(obj_literal),
                graph,
            )
        )

    def _add_triple_uri(
        self,
        subject: str,
        predicate: str,
        obj_uri: str,
        graph: pyoxigraph.NamedNode,
    ) -> None:
        self.store.add(
            pyoxigraph.Quad(
                pyoxigraph.NamedNode(subject),
                pyoxigraph.NamedNode(predicate),
                pyoxigraph.NamedNode(obj_uri),
                graph,
            )
        )


def build_vector_index(
    store: OntologyStore,
    output_path: Path,
    model_name: str = "all-MiniLM-L6-v2",
    batch_size: int = 1000,
) -> int:
    """Build vector index over all ontology terms. Returns term count embedded."""
    from .embeddings import EmbeddingStore, _build_ontology_text, _encode_texts

    logger.info("Building ontology vector index (model=%s)", model_name)

    uris: list[str] = []
    texts: list[str] = []

    for uri, label, synonyms in store.all_terms():
        text = _build_ontology_text(label, synonyms if synonyms else None)
        if not text:
            continue
        uris.append(uri)
        texts.append(text)

    if not texts:
        logger.warning("No terms to embed")
        return 0

    # Encode in batches
    import numpy as np

    all_vectors = []
    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        vectors = _encode_texts(batch, model_name)
        all_vectors.append(vectors)
        logger.info("Embedded %d/%d terms", min(i + batch_size, len(texts)), len(texts))

    vectors_array = np.vstack(all_vectors)

    # Save using EmbeddingStore
    es = EmbeddingStore(uri_col="term_uri")
    es._uris = uris
    es._texts = texts
    es._vectors = vectors_array
    es._model = model_name
    es._uri_to_idx = {uri: i for i, uri in enumerate(uris)}
    es.save(output_path, model_name=model_name)

    logger.info("Vector index: %d terms embedded → %s", len(uris), output_path)
    return len(uris)


def nearest_terms(
    query_vector,
    vectors_path: Path,
    top_k: int = 5,
) -> list[dict]:
    """Find nearest ontology terms by cosine distance."""
    from .embeddings import EmbeddingStore

    store = EmbeddingStore(uri_col="term_uri").load(vectors_path)
    results = store.nearest(query_vector, top_k=top_k)
    return [{"uri": uri, "score": score} for uri, score in results]


def load_ontology_config(path: Path | None = None) -> list[dict]:
    """Load ontology config from YAML."""
    config_path = path or _BUNDLED_CONFIG
    data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    return data.get("ontologies", [])
