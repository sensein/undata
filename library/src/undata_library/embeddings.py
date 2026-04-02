"""Semantic embedding store — precomputed vectors in parquet for similarity and alignment."""

from __future__ import annotations

import logging
import warnings
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from .utils import BASE_URI

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "all-MiniLM-L6-v2"

_EMBEDDING_MODEL = None
_EMBEDDING_MODEL_NAME: str | None = None


def _get_model(model_name: str = DEFAULT_MODEL):
    """Lazy-load sentence-transformers model."""
    global _EMBEDDING_MODEL, _EMBEDDING_MODEL_NAME
    if _EMBEDDING_MODEL is None or _EMBEDDING_MODEL_NAME != model_name:
        from sentence_transformers import SentenceTransformer

        _EMBEDDING_MODEL = SentenceTransformer(model_name)
        _EMBEDDING_MODEL_NAME = model_name
    return _EMBEDDING_MODEL


def _encode_texts(texts: list[str], model_name: str = DEFAULT_MODEL) -> np.ndarray:
    """Encode texts to embeddings. Returns (N, dim) float32 array."""
    model = _get_model(model_name)
    return model.encode(texts, show_progress_bar=False, convert_to_numpy=True)


def cosine_similarity(vec_a: np.ndarray, vec_b: np.ndarray) -> float:
    """Compute cosine similarity between two vectors."""
    norm_a = np.linalg.norm(vec_a)
    norm_b = np.linalg.norm(vec_b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(vec_a, vec_b) / (norm_a * norm_b))


class EmbeddingStore:
    """Manages precomputed embeddings stored in parquet format.

    Columns: uri/term_uri (string), text (string), vector (list[float32])
    Metadata: model (string), generated_at (ISO 8601)
    """

    def __init__(
        self,
        uri_col: str = "uri",
    ):
        self._uri_col = uri_col
        self._uris: list[str] = []
        self._texts: list[str] = []
        self._vectors: np.ndarray | None = None
        self._model: str | None = None
        self._generated_at: str | None = None
        self._uri_to_idx: dict[str, int] = {}

    @property
    def model(self) -> str | None:
        return self._model

    @property
    def size(self) -> int:
        return len(self._uris)

    def load(self, path: Path, expected_model: str | None = None) -> EmbeddingStore:
        """Load embeddings from parquet file."""
        if not path.exists():
            raise FileNotFoundError(f"Embedding store not found: {path}")

        table = pq.read_table(path)
        metadata = table.schema.metadata or {}

        self._model = metadata.get(b"model", b"").decode("utf-8") or None
        self._generated_at = metadata.get(b"generated_at", b"").decode("utf-8") or None

        if expected_model and self._model and self._model != expected_model:
            warnings.warn(
                f"Embedding model mismatch: stored={self._model}, "
                f"requested={expected_model}. Consider regenerating.",
                stacklevel=2,
            )

        self._uris = table.column(self._uri_col).to_pylist()
        self._texts = table.column("text").to_pylist()

        # Convert list[float] columns to numpy array (pure pyarrow, no pandas)
        vectors = table.column("vector").to_pylist()
        self._vectors = np.array(vectors, dtype=np.float32)

        self._uri_to_idx = {uri: i for i, uri in enumerate(self._uris)}
        return self

    def save(self, path: Path, model_name: str | None = None) -> None:
        """Save embeddings to parquet file."""
        if self._vectors is None or len(self._uris) == 0:
            raise ValueError("No embeddings to save")

        model = model_name or self._model or DEFAULT_MODEL
        generated_at = datetime.now(timezone.utc).isoformat()

        # Convert vectors to list[list[float]] for arrow
        vector_lists = [row.tolist() for row in self._vectors]

        table = pa.table(
            {
                self._uri_col: self._uris,
                "text": self._texts,
                "vector": vector_lists,
            },
            metadata={
                "model": model,
                "generated_at": generated_at,
            },
        )

        path.parent.mkdir(parents=True, exist_ok=True)
        pq.write_table(table, path)

    def get_vector(self, uri: str) -> np.ndarray | None:
        """Get embedding vector for a URI."""
        idx = self._uri_to_idx.get(uri)
        if idx is None:
            return None
        return self._vectors[idx]

    def all_vectors(self) -> np.ndarray:
        """Return all vectors as (N, dim) array."""
        if self._vectors is None:
            return np.array([], dtype=np.float32)
        return self._vectors

    def all_uris(self) -> list[str]:
        """Return all URIs."""
        return self._uris

    def similarity(self, uri_a: str, uri_b: str) -> float:
        """Compute cosine similarity between two stored embeddings."""
        vec_a = self.get_vector(uri_a)
        vec_b = self.get_vector(uri_b)
        if vec_a is None or vec_b is None:
            return 0.0
        return cosine_similarity(vec_a, vec_b)

    def nearest(self, query_vector: np.ndarray, top_k: int = 5) -> list[tuple[str, float]]:
        """Find nearest embeddings to a query vector."""
        if self._vectors is None or len(self._uris) == 0:
            return []

        # Vectorized cosine similarity
        norms = np.linalg.norm(self._vectors, axis=1)
        query_norm = np.linalg.norm(query_vector)
        if query_norm == 0:
            return []

        sims = self._vectors @ query_vector / (norms * query_norm + 1e-10)
        top_indices = np.argsort(sims)[::-1][:top_k]

        return [(self._uris[i], float(sims[i])) for i in top_indices]


def _build_element_text(element_data: dict) -> str:
    """Build embedding text from element or value.

    Elements: '{class} {name}: {description}'
    Values: '{label}: {description}' (uses semantic.label)
    """
    semantic = element_data.get("semantic", {})
    prov = element_data.get("provenance", [])

    # For values, use semantic label as primary text
    label = semantic.get("label", "")
    if label and semantic.get("value_type"):
        # This is a value concept — use label + optional description
        desc = semantic.get("description", "")
        return f"{label}: {desc}".strip(": ") if desc else label

    if not prov:
        return ""

    first = prov[0] if isinstance(prov[0], dict) else {}
    # Handle both "class" (alias) and "class_" (field name) keys
    class_ = first.get("class", "") or first.get("class_", "")
    name = first.get("name", "")
    description = first.get("description", "") or semantic.get("description", "")

    parts = []
    if class_:
        parts.append(class_)
    if name:
        parts.append(name)

    text = " ".join(parts)
    if description:
        text = f"{text}: {description}"

    return text.strip()


def _build_ontology_text(label: str, synonyms: list[str] | None = None) -> str:
    """Build embedding text from ontology term: '{label}: {synonym1}, {synonym2}'."""
    text = label
    if synonyms:
        text = f"{label}: {', '.join(synonyms)}"
    return text


def build_element_embeddings(
    elements_dir: Path,
    model_name: str = DEFAULT_MODEL,
) -> EmbeddingStore:
    """Build embeddings for all elements in directory."""
    uris: list[str] = []
    texts: list[str] = []

    for f in sorted(elements_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "semantic" not in data:
                continue
        except (yaml.YAMLError, OSError):
            continue

        uri = f"{BASE_URI}/elements/{f.stem}"
        text = _build_element_text(data)
        if not text:
            continue

        uris.append(uri)
        texts.append(text)

    if not texts:
        store = EmbeddingStore(uri_col="uri")
        store._model = model_name
        return store

    vectors = _encode_texts(texts, model_name)

    store = EmbeddingStore(uri_col="uri")
    store._uris = uris
    store._texts = texts
    store._vectors = vectors
    store._model = model_name
    store._uri_to_idx = {uri: i for i, uri in enumerate(uris)}

    return store


# NCBITaxon species relevant to neuroscience — only these (and their parents)
# are included in the embedding index to avoid 2.7M term bloat
_NCBITAXON_SPECIES_FILTER: set[str] = {
    "9606",    # Homo sapiens
    "10090",   # Mus musculus (mouse)
    "10116",   # Rattus norvegicus (rat)
    "9544",    # Macaca mulatta (rhesus macaque)
    "9483",    # Callithrix jacchus (marmoset)
    "7955",    # Danio rerio (zebrafish)
    "7227",    # Drosophila melanogaster (fruit fly)
    "6239",    # Caenorhabditis elegans (nematode)
    "9541",    # Macaca fascicularis (crab-eating macaque)
    "9598",    # Pan troglodytes (chimpanzee)
    "9615",    # Canis lupus familiaris (dog)
    "9986",    # Oryctolagus cuniculus (rabbit)
    "9685",    # Felis catus (cat)
    "9823",    # Sus scrofa (pig)
    "9031",    # Gallus gallus (chicken)
    "8364",    # Xenopus tropicalis (frog)
    "13616",   # Monodelphis domestica (opossum)
    "28377",   # Anolis carolinensis (green anole)
    "7740",    # Branchiostoma floridae (amphioxus)
    "69293",   # Gasterosteus aculeatus (stickleback)
}


def _is_ncbitaxon_relevant(term_uri: str) -> bool:
    """Check if an NCBITaxon term should be included in the embedding index."""
    # Extract the taxon ID from the URI (e.g., http://purl.obolibrary.org/obo/NCBITaxon_9606)
    if "NCBITaxon_" not in term_uri:
        return True  # not NCBITaxon, include
    taxon_id = term_uri.rsplit("NCBITaxon_", 1)[-1]
    return taxon_id in _NCBITAXON_SPECIES_FILTER


def build_ontology_embeddings(
    cache_dir: Path,
    model_name: str = DEFAULT_MODEL,
) -> EmbeddingStore:
    """Build embeddings for all ontology terms in cache.

    NCBITaxon is filtered to neuroscience-relevant species only (~20 terms)
    to prevent the 2.7M term ontology from diluting the embedding index.
    """
    term_uris: list[str] = []
    texts: list[str] = []

    for f in sorted(cache_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "terms" not in data:
                continue
        except (yaml.YAMLError, OSError):
            continue

        for term_uri, info in data["terms"].items():
            if not isinstance(info, dict):
                continue
            label = info.get("label", "")
            if not label:
                continue
            # Filter NCBITaxon to relevant species only
            if not _is_ncbitaxon_relevant(term_uri):
                continue
            synonyms = info.get("synonyms", [])
            text = _build_ontology_text(label, synonyms)

            term_uris.append(term_uri)
            texts.append(text)

    if not texts:
        store = EmbeddingStore(uri_col="term_uri")
        store._model = model_name
        return store

    vectors = _encode_texts(texts, model_name)

    store = EmbeddingStore(uri_col="term_uri")
    store._uris = term_uris
    store._texts = texts
    store._vectors = vectors
    store._model = model_name
    store._uri_to_idx = {uri: i for i, uri in enumerate(term_uris)}

    return store
