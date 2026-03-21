"""Enrichment pipeline: post-ingestion enrichment of elements."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .embeddings import EmbeddingStore, build_element_embeddings, build_ontology_embeddings
from .hashing import canonical_json, compute_sha256, generate_short_key

logger = logging.getLogger(__name__)


def enrich_elements(
    elements_dir: Path,
    cache_dir: Path,
    library_path: Path | None = None,
    model_name: str = "all-MiniLM-L6-v2",
    threshold: float = 0.7,
    dry_run: bool = False,
) -> dict[str, int]:
    """Enrich elements: auto-assign ontology_term, resolve response_options, populate value_domain.

    Returns stats: {enriched_new, enriched_unchanged, ontology_assigned, values_resolved,
                    value_domain_set, total}
    """
    lib_path = library_path or elements_dir.parent

    # Load ontology embeddings for ontology_term assignment
    onto_store = _load_ontology_embeddings(cache_dir, model_name)

    # Load element embeddings for matching
    elem_store = _load_or_build_element_embeddings(elements_dir, model_name)

    # Load ontology cache for metadata
    onto_cache = _load_ontology_cache(cache_dir)

    # Load value concepts for response_option resolution
    values_dir = lib_path / "values"
    value_lookup = _build_value_lookup(values_dir) if values_dir.exists() else {}

    stats = {
        "enriched_new": 0,
        "enriched_unchanged": 0,
        "ontology_assigned": 0,
        "values_resolved": 0,
        "value_domain_set": 0,
        "total": 0,
    }

    new_elements: list[Path] = []

    for f in sorted(elements_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "semantic" not in data:
                continue
        except (yaml.YAMLError, OSError):
            continue

        stats["total"] += 1
        sem = data["semantic"]
        changed_identity = False
        changed_metadata = False

        # 1. Auto-assign ontology_term via embedding distance
        if not sem.get("ontology_term") and onto_store is not None and elem_store is not None:
            uri = f"https://schema.undata.live/elements/{f.stem}"
            assigned = _assign_ontology_term(uri, elem_store, onto_store, onto_cache, threshold)
            if assigned:
                sem["ontology_term"] = assigned
                changed_identity = True
                stats["ontology_assigned"] += 1

        # 2. Resolve response_options to ValueConcept URIs
        if sem.get("response_options") and value_lookup:
            resolved_count = _resolve_response_options(sem, value_lookup)
            if resolved_count > 0:
                stats["values_resolved"] += resolved_count
                changed_metadata = True

        # 3. Auto-populate value_domain
        if not sem.get("value_domain"):
            domain = _populate_value_domain(sem)
            if domain:
                sem["value_domain"] = domain
                changed_metadata = True
                stats["value_domain_set"] += 1

        if not changed_identity and not changed_metadata:
            stats["enriched_unchanged"] += 1
            continue

        if changed_identity:
            # Identity changed → create new element with new URI
            if not dry_run:
                new_path = _create_enriched_element(data, sem, f, lib_path)
                new_elements.append(new_path)
            stats["enriched_new"] += 1
        else:
            # Only metadata changed → update in place
            if not dry_run:
                data["semantic"] = sem
                f.write_text(
                    yaml.dump(data, default_flow_style=False, sort_keys=False),
                    encoding="utf-8",
                )

    # Regenerate embeddings if new elements were created
    if new_elements and not dry_run:
        try:
            store = build_element_embeddings(elements_dir, model_name=model_name)
            store.save(lib_path / "embeddings.parquet", model_name=model_name)
        except ImportError:
            logger.warning("sentence-transformers not installed; skipping embedding regeneration")

    return stats


def _load_ontology_embeddings(cache_dir: Path, model_name: str) -> EmbeddingStore | None:
    """Load ontology embeddings from vector index (024) or legacy cache."""
    # Ontology vectors in cache dir (~/.cache/undata/ontology-vectors.parquet)
    cache_base = Path.home() / ".cache" / "undata"
    for candidate in [
        cache_base / "ontology-vectors.parquet",
        cache_dir / "ontology-vectors.parquet",  # fallback
    ]:
        if candidate.exists():
            try:
                store = EmbeddingStore(uri_col="term_uri").load(
                    candidate, expected_model=model_name
                )
                if store.size > 0:
                    logger.info(
                        "Loaded ontology embeddings from %s: %d terms", candidate, store.size
                    )
                    return store
            except Exception:
                pass

    # Try to build from legacy cache files
    try:
        store = build_ontology_embeddings(cache_dir, model_name=model_name)
        if store.size > 0:
            store.save(cache_dir / "embeddings.parquet", model_name=model_name)
            return store
    except ImportError:
        logger.warning(
            "sentence-transformers not installed; ontology embedding matching unavailable"
        )
    return None


def _load_or_build_element_embeddings(elements_dir: Path, model_name: str) -> EmbeddingStore | None:
    """Load or build element embeddings."""
    parquet_path = elements_dir.parent / "embeddings.parquet"
    if parquet_path.exists():
        try:
            store = EmbeddingStore(uri_col="uri").load(parquet_path, expected_model=model_name)
            if store.size > 0:
                return store
        except Exception:
            pass

    try:
        store = build_element_embeddings(elements_dir, model_name=model_name)
        if store.size > 0:
            store.save(parquet_path, model_name=model_name)
            return store
    except ImportError:
        logger.warning("sentence-transformers not installed; embedding matching unavailable")
    return None


def _load_ontology_cache(cache_dir: Path) -> dict[str, dict]:
    """Load ontology term metadata from cache YAML files."""
    cache: dict[str, dict] = {}
    if not cache_dir.exists():
        return cache

    for f in sorted(cache_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "terms" not in data:
                continue
            for term_uri, info in data["terms"].items():
                if isinstance(info, dict):
                    cache[term_uri] = info
        except (yaml.YAMLError, OSError):
            continue
    return cache


def _assign_ontology_annotations(
    element_uri: str,
    elem_store: EmbeddingStore,
    onto_store: EmbeddingStore,
    onto_cache: dict[str, dict],
    threshold: float,
    is_value: bool = False,
    model_name: str = "all-MiniLM-L6-v2",
    max_annotations: int = 10,
    gap_threshold: float = 0.15,
) -> list[dict]:
    """Assign multiple ontology annotations via embedding similarity.

    Returns list of OntologyAnnotation-compatible dicts.
    Heuristic: threshold + gap cutoff + max cap.
    """
    from .models import MatchLevel

    vec = elem_store.get_vector(element_uri)
    if vec is None:
        return []

    results = onto_store.nearest(vec, top_k=20)
    if not results:
        return []

    annotations = []
    prev_score = None

    for uri, score in results:
        if score < threshold:
            break
        # Gap cutoff
        if prev_score is not None and (prev_score - score) > gap_threshold:
            break
        if len(annotations) >= max_annotations:
            break

        # Skip deprecated terms
        term_info = onto_cache.get(uri, {})
        if term_info.get("deprecated", False):
            continue

        label = term_info.get("label", "")
        # Determine ontology from URI
        ontology = _ontology_from_uri(uri)
        # SKOS relation from score
        mapping_relation = _score_to_skos(score)
        # Match level
        match_level = (
            MatchLevel.element_match if is_value and score >= 0.9 else MatchLevel.concept_match
        )

        annotations.append(
            {
                "term_uri": uri,
                "term_label": label,
                "ontology": ontology,
                "mapping_relation": mapping_relation,
                "match_level": match_level.value,
                "score": round(score, 4),
                "model": model_name,
                "primary": len(annotations) == 0,  # first = primary
            }
        )
        prev_score = score

    return annotations


def _assign_ontology_term(
    element_uri: str,
    elem_store: EmbeddingStore,
    onto_store: EmbeddingStore,
    onto_cache: dict[str, dict],
    threshold: float,
) -> str | None:
    """Legacy single-term assignment. Returns primary term URI or None."""
    annotations = _assign_ontology_annotations(
        element_uri, elem_store, onto_store, onto_cache, threshold
    )
    if not annotations:
        return None
    return annotations[0]["term_uri"]


def _score_to_skos(score: float) -> str:
    """Map cosine similarity to SKOS mapping relation."""
    if score >= 0.95:
        return "skos:exactMatch"
    if score >= 0.8:
        return "skos:closeMatch"
    if score >= 0.5:
        return "skos:relatedMatch"
    return "skos:noMatch"  # Below threshold — should not be used (filtered earlier)


def _ontology_from_uri(uri: str) -> str:
    """Extract ontology prefix from term URI."""
    # http://purl.obolibrary.org/obo/NCIT_C25150 → ncit
    if "/obo/" in uri:
        part = uri.rsplit("/obo/", 1)[-1]
        prefix = part.split("_")[0]
        return prefix.lower()
    return "unknown"


def _resolve_response_options(sem: dict, value_lookup: dict[str, str]) -> int:
    """Resolve response_option values to ValueConcept URIs. Returns count resolved."""
    opts = sem.get("response_options", [])
    resolved = 0
    for opt in opts:
        if not isinstance(opt, dict):
            continue
        value = opt.get("value", "")
        label = opt.get("label", "")
        # Skip if already a URI
        if value.startswith("https://"):
            continue
        # Match by value or label
        key = value.lower()
        if key in value_lookup:
            opt["ontology_term"] = value_lookup[key]
            resolved += 1
        elif label and label.lower() in value_lookup:
            opt["ontology_term"] = value_lookup[label.lower()]
            resolved += 1
    return resolved


def _populate_value_domain(sem: dict) -> str | None:
    """Auto-populate value_domain from data_type."""
    if sem.get("response_options"):
        return "categorical"

    dt = sem.get("data_type", "")
    mapping = {
        "string": "text",
        "integer": "numeric",
        "float": "numeric",
        "boolean": "boolean",
    }
    return mapping.get(dt)


def _build_value_lookup(values_dir: Path) -> dict[str, str]:
    """Build a lookup: lowercase label/raw_value → ValueConcept URI."""
    lookup: dict[str, str] = {}
    for f in sorted(values_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "semantic" not in data:
                continue
            sem = data["semantic"]
            label = sem.get("label", "")
            uri = f"https://schema.undata.live/values/{f.stem}"
            if label:
                lookup[label.lower()] = uri
            # Also index raw_value from provenance
            for p in data.get("provenance", []):
                raw = p.get("raw_value", "")
                if raw:
                    lookup[raw.lower()] = uri
        except (yaml.YAMLError, OSError):
            continue
    return lookup


def _create_enriched_element(
    original_data: dict,
    new_semantic: dict,
    original_path: Path,
    library_path: Path,
) -> Path:
    """Create a new element file with enriched semantic identity."""

    # Compute new hash
    canonical = canonical_json(new_semantic)
    sha = compute_sha256(canonical)
    key = generate_short_key(sha)

    # Get attribute name from first provenance
    prov = original_data.get("provenance", [{}])
    name = prov[0].get("name", "unknown") if prov else "unknown"

    # Build old URI for derived_from
    old_uri = f"https://schema.undata.live/elements/{original_path.stem}"

    # Create enrichment provenance entry
    now_iso = datetime.now(timezone.utc).isoformat()
    enrichment_prov = {
        "source": "enrichment",
        "class": prov[0].get("class", "") if prov else "",
        "name": name,
        "generated_at": now_iso,
        "attributed_to": "urn:undata:enrichment-pipeline",
        "activity": "enrichment",
        "derived_from": old_uri,
    }

    # New element data with enriched semantic + original provenance + enrichment entry
    new_data = {
        "sha256": sha,
        "semantic": new_semantic,
        "provenance": list(original_data.get("provenance", [])) + [enrichment_prov],
    }

    # Write new file
    elements_dir = library_path / "elements"
    safe_name = name.lower().replace("/", "_").replace(":", "_").replace("\\", "_")
    if len(safe_name) > 60:
        safe_name = safe_name[:60]
    filename = f"{safe_name}_{key}.yaml"
    new_path = elements_dir / filename
    new_path.write_text(
        yaml.dump(new_data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )

    return new_path
