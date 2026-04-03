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


def compute_entity_embeddings(
    entities: list[dict],
    model_name: str = DEFAULT_MODEL,
) -> list[dict]:
    """Compute embeddings for a batch of entities (any type) and add to each dict.

    Sets entity["embedding"] = list[float] (384-dim).
    Returns the same entities with embeddings added.
    """
    texts = [_build_element_text(e) for e in entities]
    non_empty = [(i, t) for i, t in enumerate(texts) if t]

    if not non_empty:
        return entities

    indices, valid_texts = zip(*non_empty)
    vectors = _encode_texts(list(valid_texts), model_name)

    for idx, vec in zip(indices, vectors):
        entities[idx]["embedding"] = vec.tolist()

    return entities


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


# NCBITaxon filter for neuroscience-relevant organisms.
# Includes genus, species, AND subspecies/strains for each model organism.
# Without this filter, NCBITaxon's 2.7M terms overwhelm the embedding index.
_NCBITAXON_SPECIES_FILTER: set[str] = {
    # --- Homo (human) ---
    "9605",  # Homo (genus)
    "9606",  # Homo sapiens
    "63221",  # Homo sapiens neanderthalensis
    # --- Mus (mouse) ---
    "10088",  # Mus (genus)
    "10090",  # Mus musculus
    "10091",  # Mus musculus domesticus
    "10092",  # Mus musculus musculus
    "10093",  # Mus musculus castaneus
    "35531",  # Mus musculus bactrianus
    "947985",  # Mus musculus molossinus (Japanese lab mouse)
    "39442",  # Mus spretus
    # --- Rattus (rat) ---
    "10114",  # Rattus (genus)
    "10116",  # Rattus norvegicus
    "10117",  # Rattus rattus
    # --- Macaca (macaques) ---
    "9539",  # Macaca (genus)
    "9541",  # Macaca fascicularis (crab-eating)
    "9544",  # Macaca mulatta (rhesus)
    "9545",  # Macaca nemestrina (pig-tailed)
    "9548",  # Macaca fuscata (Japanese)
    # --- Other primates ---
    "9443",  # Primates (order)
    "9479",  # Callithricidae (family — marmosets/tamarins)
    "9483",  # Callithrix jacchus (marmoset)
    "9593",  # Gorilla (genus)
    "9598",  # Pan troglodytes (chimpanzee)
    "9597",  # Pan paniscus (bonobo)
    "9600",  # Pongo (genus)
    "9606",  # Homo sapiens (duplicated for clarity)
    # --- Capuchins (BBQS) ---
    "9527",  # Cebidae (family)
    "118643",  # Sapajus (genus — robust capuchins)
    "9515",  # Sapajus apella (brown capuchin / tufted capuchin)
    # --- Danio (zebrafish) ---
    "7954",  # Danio (genus)
    "7955",  # Danio rerio
    # --- Drosophila (fruit fly) ---
    "7215",  # Drosophila (genus)
    "7227",  # Drosophila melanogaster
    # --- C. elegans (nematode) ---
    "6237",  # Caenorhabditis (genus)
    "6239",  # Caenorhabditis elegans
    # --- Dog ---
    "9611",  # Canis (genus)
    "9612",  # Canis lupus
    "9615",  # Canis lupus familiaris
    # --- Cat ---
    "9681",  # Felis (genus)
    "9685",  # Felis catus
    # --- Rabbit ---
    "9984",  # Oryctolagus (genus)
    "9986",  # Oryctolagus cuniculus
    # --- Pig ---
    "9821",  # Sus (genus)
    "9823",  # Sus scrofa
    "9825",  # Sus scrofa domesticus
    # --- Chicken ---
    "9030",  # Gallus (genus)
    "9031",  # Gallus gallus
    # --- Frog ---
    "8353",  # Xenopus (genus)
    "8355",  # Xenopus laevis
    "8364",  # Xenopus tropicalis
    # --- Sheep (neuroscience model) ---
    "9935",  # Ovis (genus)
    "9940",  # Ovis aries
    # --- Ferret (visual neuroscience) ---
    "9668",  # Mustela (genus)
    "9669",  # Mustela putorius furo (ferret)
    # --- Tree shrew (visual neuroscience) ---
    "37347",  # Tupaia (genus)
    "37348",  # Tupaia belangeri
    # --- Opossum ---
    "13615",  # Monodelphis (genus)
    "13616",  # Monodelphis domestica
    # --- Songbirds (vocal learning) ---
    "44394",  # Taeniopygia (genus)
    "59729",  # Taeniopygia guttata (zebra finch)
    "48883",  # Melopsittacus undulatus (budgerigar)
    # --- Octopus (cephalopod neuroscience) ---
    "6644",  # Octopus (genus)
    "6645",  # Octopus vulgaris
    # --- Aplysia (learning/memory) ---
    "6499",  # Aplysia (genus)
    "6500",  # Aplysia californica
    # --- Lamprey (motor systems) ---
    "7745",  # Petromyzon (genus)
    "7757",  # Petromyzon marinus
    # --- Gerbil (BBQS — auditory neuroscience) ---
    "10046",  # Meriones (genus)
    "10047",  # Meriones unguiculatus (Mongolian gerbil)
    # --- Cowbird (BBQS — social songbird) ---
    "84832",  # Molothrus (genus)
    "84833",  # Molothrus ater (brown-headed cowbird)
    # --- Cichlids (BBQS — social/evolutionary neuroscience) ---
    "8113",  # Cichlidae (family)
    "32507",  # Astatotilapia (genus)
    "8153",  # Oreochromis (genus — tilapia)
    # --- Acoel worm (BBQS — regeneration neuroscience) ---
    "286301",  # Hofstenia (genus)
    "286302",  # Hofstenia miamia (panther worm)
    # --- Other model organisms in neuroscience ---
    "7740",  # Branchiostoma floridae (amphioxus — basal chordate)
    "69293",  # Gasterosteus aculeatus (stickleback — behavioral genetics)
    "28377",  # Anolis carolinensis (green anole — neuroethology)
    # --- Key higher taxonomic ranks ---
    "40674",  # Mammalia (class)
    "8287",  # Sarcopterygii (lobe-finned fishes + tetrapods)
    "7742",  # Vertebrata (subphylum)
    "33208",  # Metazoa (kingdom — all animals)
    "7711",  # Chordata (phylum)
    "6072",  # Eumetazoa (animals with nervous systems)
}


def _is_ncbitaxon_relevant(term_uri: str) -> bool:
    """Check if an NCBITaxon term should be included in the embedding index.

    Includes genus, species, and subspecies for neuroscience model organisms,
    plus key higher taxonomic ranks for context.
    """
    if "NCBITaxon_" not in term_uri:
        return True  # not NCBITaxon, include everything else
    taxon_id = term_uri.rsplit("NCBITaxon_", 1)[-1]
    return taxon_id in _NCBITAXON_SPECIES_FILTER


def build_ontology_embeddings(
    cache_dir: Path,
    model_name: str = DEFAULT_MODEL,
) -> EmbeddingStore:
    """Build embeddings for all ontology terms from pyoxigraph store.

    Reads directly from the ontology store (no YAML cache needed).
    NCBITaxon is filtered to neuroscience-relevant species only (~90 taxa).
    """
    term_uris: list[str] = []
    texts: list[str] = []

    # Primary: read from pyoxigraph store (fast, no YAML files)
    store_path = Path.home() / ".cache" / "undata" / "ontology-store"
    if store_path.exists():
        try:
            from .ontology_store import OntologyStore

            onto_store = OntologyStore(store_path)
            for uri, label, synonyms in onto_store.all_terms():
                if not label:
                    continue
                if not _is_ncbitaxon_relevant(uri):
                    continue
                text = _build_ontology_text(label, synonyms)
                term_uris.append(uri)
                texts.append(text)
            logger.info("Read %d terms from ontology store for embedding", len(term_uris))
        except Exception as exc:
            logger.warning("Failed to read ontology store: %s", exc)

    # Fallback: legacy YAML cache files
    if not texts and cache_dir.exists():
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
