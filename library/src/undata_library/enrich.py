"""Enrichment pipeline: in-place enrichment of staged registry entities.

Enrichment adds metadata (ontology_annotations, value_domain) to staged entities
WITHOUT creating new entities. All updates are in-place.

Dependency order: elements + values → valuesets → schemas.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from .embeddings import EmbeddingStore, build_element_embeddings, build_ontology_embeddings
from .utils import BASE_URI, safe_load_yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# In-place update (T023)
# ---------------------------------------------------------------------------


def _update_entity_in_place(
    filepath: Path,
    ontology_annotations: list[dict] | None = None,
    value_domain: str | None = None,
    description: str | None = None,
) -> bool:
    """Update a staged entity file in-place with enrichment metadata.

    Only writes fields that are provided and non-None.
    Returns True if any change was made.
    """
    data = safe_load_yaml(filepath)
    if data is None or "semantic" not in data:
        return False

    sem = data["semantic"]
    changed = False

    if ontology_annotations is not None and ontology_annotations:
        sem["ontology_annotations"] = ontology_annotations
        changed = True

    if value_domain is not None and not sem.get("value_domain"):
        sem["value_domain"] = value_domain
        changed = True

    if description is not None and not sem.get("description"):
        sem["description"] = description
        changed = True

    if changed:
        filepath.write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    return changed


# ---------------------------------------------------------------------------
# Element enrichment (T024)
# ---------------------------------------------------------------------------


def enrich_elements(
    staging_dir: Path,
    cache_dir: Path | None = None,
    onto_store: EmbeddingStore | None = None,
    onto_cache: dict[str, dict] | None = None,
    model_name: str = "all-MiniLM-L6-v2",
    threshold: float = 0.7,
    dry_run: bool = False,
    use_llm: bool = False,
) -> dict[str, int]:
    """Enrich staged elements in-place: assign ontology_annotations, populate value_domain.

    Works on staging_dir/elements/. No new files are created.
    If use_llm=True, the candidate threshold drops to 0.4 and borderline matches
    (0.4-0.7) are verified by LLM before assignment. Without LLM, only matches
    above threshold (0.7) are auto-assigned.

    Returns stats: {ontology_assigned, value_domain_set, values_resolved, unchanged, total}
    """
    elements_dir = staging_dir / "elements"
    if not elements_dir.exists():
        return {
            "ontology_assigned": 0,
            "value_domain_set": 0,
            "values_resolved": 0,
            "unchanged": 0,
            "total": 0,
        }

    # Load ontology embeddings if not provided
    if onto_store is None and cache_dir is not None:
        onto_store = _load_ontology_embeddings(cache_dir, model_name)
    if onto_cache is None and cache_dir is not None:
        onto_cache = _load_ontology_cache(cache_dir)
    onto_cache = onto_cache or {}

    # Build element embeddings for matching
    elem_store = _load_or_build_element_embeddings(elements_dir, model_name)

    # Load value concepts for response_option resolution
    values_dir = staging_dir / "values"
    value_lookup = _build_value_lookup(values_dir) if values_dir.exists() else {}

    stats = {
        "ontology_assigned": 0,
        "value_domain_set": 0,
        "values_resolved": 0,
        "unchanged": 0,
        "total": 0,
    }

    for f in sorted(elements_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "semantic" not in data:
                continue
        except (yaml.YAMLError, OSError):
            continue

        stats["total"] += 1
        sem = data["semantic"]
        annotations = None
        domain = None

        # 1. Assign ontology_annotations via embedding + optional LLM verification
        if (
            not sem.get("ontology_annotations")
            and onto_store is not None
            and elem_store is not None
        ):
            uri = f"{BASE_URI}/elements/{f.stem}"
            # Build description for LLM context
            prov = data.get("provenance", [{}])
            first_prov = prov[0] if prov and isinstance(prov[0], dict) else {}
            elem_desc = f"{first_prov.get('class', '')} {first_prov.get('name', '')}"
            desc = first_prov.get("description") or sem.get("description", "")
            if desc:
                elem_desc = f"{elem_desc}: {desc}"
            source_ctx = f"source={first_prov.get('source', '')}"

            # Use lower threshold for candidate retrieval when LLM is available
            effective_threshold = 0.4 if use_llm else threshold
            annotations = _assign_ontology_annotations(
                uri,
                elem_store,
                onto_store,
                onto_cache,
                effective_threshold,
                model_name=model_name,
                use_llm=use_llm,
                element_desc=elem_desc.strip(),
                source_context=source_ctx,
            )
            if annotations:
                stats["ontology_assigned"] += 1

        # 2. Resolve response_options to ValueConcept URIs
        if sem.get("response_options") and value_lookup:
            resolved_count = _resolve_response_options(sem, value_lookup)
            if resolved_count > 0:
                stats["values_resolved"] += resolved_count
                # Write the resolved options back
                if not dry_run:
                    data["semantic"] = sem
                    f.write_text(
                        yaml.dump(data, default_flow_style=False, sort_keys=False),
                        encoding="utf-8",
                    )

        # 3. Auto-populate value_domain
        if not sem.get("value_domain"):
            domain = _populate_value_domain(sem)
            if domain:
                stats["value_domain_set"] += 1

        if annotations or domain:
            if not dry_run:
                _update_entity_in_place(f, ontology_annotations=annotations, value_domain=domain)
        else:
            stats["unchanged"] += 1

    return stats


# ---------------------------------------------------------------------------
# Value enrichment (T025)
# ---------------------------------------------------------------------------


def enrich_from_source_metadata(staging_dir: Path) -> dict[str, int]:
    """Pre-enrich entities that already have ontology identifiers from their source.

    openMINDS instances have preferredOntologyIdentifier; other sources may have
    similar fields. This step assigns high-confidence annotations without
    embedding lookup or LLM verification.
    """
    from .models import MatchLevel

    stats = {"assigned": 0, "total": 0}

    for entity_type in ("elements", "values", "schemas", "valuesets"):
        entity_dir = staging_dir / entity_type
        if not entity_dir.exists():
            continue

        for f in sorted(entity_dir.glob("*.yaml")):
            data = safe_load_yaml(f)
            if data is None or "semantic" not in data:
                continue
            stats["total"] += 1

            sem = data["semantic"]
            if sem.get("ontology_annotations"):
                continue  # Already annotated

            # Check provenance for ontology identifiers
            prov_list = data.get("provenance", [])
            if not prov_list:
                continue
            first_prov = prov_list[0] if isinstance(prov_list[0], dict) else {}

            # openMINDS instances: check for meaning field (set by LinkML adapter from PermissibleValue.meaning)
            # Also check description for ontology URIs
            onto_uri = None
            desc = first_prov.get("description", "") or sem.get("description", "") or ""

            # Check for OBO URIs in description
            import re

            obo_match = re.search(r"(http://purl\.obolibrary\.org/obo/\w+)", desc)
            if obo_match:
                onto_uri = obo_match.group(1)

            # Check semantic dict for ontology_id or meaning
            if sem.get("ontology_id"):
                onto_uri = sem["ontology_id"]

            if onto_uri:
                annotation = {
                    "term_uri": onto_uri,
                    "term_label": first_prov.get("name", ""),
                    "ontology": _ontology_from_uri(onto_uri),
                    "mapping_relation": "skos:exactMatch",
                    "match_level": MatchLevel.element_match.value
                    if entity_type == "values"
                    else MatchLevel.concept_match.value,
                    "score": 1.0,
                    "model": "source_metadata",
                    "primary": True,
                }
                _update_entity_in_place(f, ontology_annotations=[annotation])
                stats["assigned"] += 1

    return stats


def enrich_values(
    staging_dir: Path,
    cache_dir: Path | None = None,
    onto_store: EmbeddingStore | None = None,
    onto_cache: dict[str, dict] | None = None,
    model_name: str = "all-MiniLM-L6-v2",
    threshold: float = 0.7,
    use_llm: bool = False,
) -> dict[str, int]:
    """Enrich staged values in-place: assign ontology_annotations with element_match for high scores.

    Returns stats: {ontology_assigned, unchanged, total}
    """
    values_dir = staging_dir / "values"
    if not values_dir.exists():
        return {"ontology_assigned": 0, "unchanged": 0, "total": 0}

    if onto_store is None and cache_dir is not None:
        onto_store = _load_ontology_embeddings(cache_dir, model_name)
    if onto_cache is None and cache_dir is not None:
        onto_cache = _load_ontology_cache(cache_dir)
    onto_cache = onto_cache or {}

    # Build value embeddings
    elem_store = _load_or_build_element_embeddings(values_dir, model_name)

    stats = {"ontology_assigned": 0, "unchanged": 0, "total": 0}

    for f in sorted(values_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "semantic" not in data:
                continue
        except (yaml.YAMLError, OSError):
            continue

        stats["total"] += 1
        sem = data["semantic"]

        if sem.get("ontology_annotations"):
            stats["unchanged"] += 1
            continue

        if onto_store is None or elem_store is None:
            stats["unchanged"] += 1
            continue

        uri = f"{BASE_URI}/elements/{f.stem}"
        annotations = _assign_ontology_annotations(
            uri,
            elem_store,
            onto_store,
            onto_cache,
            threshold,
            is_value=True,
            model_name=model_name,
        )

        if annotations:
            _update_entity_in_place(f, ontology_annotations=annotations)
            stats["ontology_assigned"] += 1
        else:
            stats["unchanged"] += 1

    return stats


# ---------------------------------------------------------------------------
# Schema enrichment (T026)
# ---------------------------------------------------------------------------


def enrich_schemas(
    staging_dir: Path,
    cache_dir: Path | None = None,
    onto_store: EmbeddingStore | None = None,
    onto_cache: dict[str, dict] | None = None,
    model_name: str = "all-MiniLM-L6-v2",
    threshold: float = 0.7,
) -> dict[str, int]:
    """Enrich staged schemas in-place: assign ontology_annotations (concept_match).

    Returns stats: {ontology_assigned, unchanged, total}
    """
    schemas_dir = staging_dir / "schemas"
    if not schemas_dir.exists():
        return {"ontology_assigned": 0, "unchanged": 0, "total": 0}

    if onto_store is None and cache_dir is not None:
        onto_store = _load_ontology_embeddings(cache_dir, model_name)
    if onto_cache is None and cache_dir is not None:
        onto_cache = _load_ontology_cache(cache_dir)
    onto_cache = onto_cache or {}

    # Build schema embeddings
    elem_store = _load_or_build_element_embeddings(schemas_dir, model_name)

    stats = {"ontology_assigned": 0, "unchanged": 0, "total": 0}

    for f in sorted(schemas_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "semantic" not in data:
                continue
        except (yaml.YAMLError, OSError):
            continue

        stats["total"] += 1
        sem = data["semantic"]

        if sem.get("ontology_annotations"):
            stats["unchanged"] += 1
            continue

        if onto_store is None or elem_store is None:
            stats["unchanged"] += 1
            continue

        uri = f"{BASE_URI}/elements/{f.stem}"
        # Schemas always get concept_match (not element_match)
        annotations = _assign_ontology_annotations(
            uri,
            elem_store,
            onto_store,
            onto_cache,
            threshold,
            is_value=False,
            model_name=model_name,
        )

        if annotations:
            _update_entity_in_place(f, ontology_annotations=annotations)
            stats["ontology_assigned"] += 1
        else:
            stats["unchanged"] += 1

    return stats


# ---------------------------------------------------------------------------
# Valueset enrichment (T027)
# ---------------------------------------------------------------------------


def enrich_valuesets(
    staging_dir: Path,
) -> dict[str, int]:
    """Enrich staged valuesets in-place: derive ontology_annotations from enriched member values.

    This runs AFTER enrich_values(), so member values already have ontology_annotations.
    Valuesets inherit the most common ontology namespace from their members.

    Returns stats: {enriched, unchanged, total}
    """
    valuesets_dir = staging_dir / "valuesets"
    if not valuesets_dir.exists():
        return {"enriched": 0, "unchanged": 0, "total": 0}

    # Build a lookup of value labels → ontology info from enriched values
    values_dir = staging_dir / "values"
    value_ontology_map = _build_value_ontology_map(values_dir) if values_dir.exists() else {}

    stats = {"enriched": 0, "unchanged": 0, "total": 0}

    for f in sorted(valuesets_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "semantic" not in data:
                continue
        except (yaml.YAMLError, OSError):
            continue

        stats["total"] += 1
        sem = data["semantic"]

        if sem.get("ontology_annotations"):
            stats["unchanged"] += 1
            continue

        # Derive ontology namespace from members
        members = sem.get("members", [])
        if not members and not value_ontology_map:
            stats["unchanged"] += 1
            continue

        # Collect ontology annotations from member values
        ontology_counts: dict[str, int] = {}
        best_annotation = None
        best_score = 0.0

        for member_uri in members:
            member_anns = value_ontology_map.get(member_uri, [])
            for ann in member_anns:
                onto = ann.get("ontology", "unknown")
                ontology_counts[onto] = ontology_counts.get(onto, 0) + 1
                if ann.get("score", 0) > best_score:
                    best_score = ann["score"]
                    best_annotation = ann

        if best_annotation:
            # Create a valueset-level annotation from the dominant ontology
            vs_annotation = {
                "term_uri": best_annotation["term_uri"],
                "term_label": best_annotation.get("term_label", ""),
                "ontology": best_annotation.get("ontology", "unknown"),
                "mapping_relation": "skos:relatedMatch",
                "match_level": "concept_match",
                "score": round(best_score, 4),
                "model": best_annotation.get("model", ""),
                "primary": True,
            }
            _update_entity_in_place(f, ontology_annotations=[vs_annotation])
            stats["enriched"] += 1
        else:
            stats["unchanged"] += 1

    return stats


def _build_value_ontology_map(values_dir: Path) -> dict[str, list[dict]]:
    """Build a lookup: value URI → ontology_annotations from enriched value files."""
    mapping: dict[str, list[dict]] = {}
    for f in sorted(values_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "semantic" not in data:
                continue
            anns = data["semantic"].get("ontology_annotations", [])
            if anns:
                # Use both stem-based URI and any label-based keys
                uri = f"{BASE_URI}/elements/{f.stem}"
                mapping[uri] = anns
                label = data["semantic"].get("label", "")
                if label:
                    mapping[label.lower()] = anns
        except (yaml.YAMLError, OSError):
            continue
    return mapping


# ---------------------------------------------------------------------------
# Orchestrator (T028)
# ---------------------------------------------------------------------------


def enrich_all(
    staging_dir: Path,
    cache_dir: Path | None = None,
    onto_store: EmbeddingStore | None = None,
    onto_cache: dict[str, dict] | None = None,
    model_name: str = "all-MiniLM-L6-v2",
    threshold: float = 0.7,
    use_llm: bool = False,
) -> dict[str, dict]:
    """Orchestrate enrichment of all entity types in dependency order.

    Order: (0) source metadata  (1) elements + values  (2) valuesets  (3) schemas

    When use_llm=True, candidate threshold drops to 0.4 and borderline matches
    are verified by LLM. Without LLM, only matches above threshold are auto-assigned.

    Returns: {source_metadata: {...}, elements: {...}, values: {...}, valuesets: {...}, schemas: {...}}
    """
    # Load shared resources once
    if onto_store is None and cache_dir is not None:
        onto_store = _load_ontology_embeddings(cache_dir, model_name)
    if onto_cache is None and cache_dir is not None:
        onto_cache = _load_ontology_cache(cache_dir)

    results: dict[str, dict] = {}

    # Phase 0: Pre-enrich from source metadata (ontology IDs already in source data)
    logger.info("Pre-enriching from source metadata...")
    results["source_metadata"] = enrich_from_source_metadata(staging_dir)

    # Phase 1: elements + values (independent of each other)
    logger.info("Enriching elements...")
    results["elements"] = enrich_elements(
        staging_dir,
        cache_dir=None,
        onto_store=onto_store,
        onto_cache=onto_cache,
        model_name=model_name,
        threshold=threshold,
        use_llm=use_llm,
    )
    logger.info("Enriching values...")
    results["values"] = enrich_values(
        staging_dir,
        cache_dir=None,
        onto_store=onto_store,
        onto_cache=onto_cache,
        model_name=model_name,
        threshold=threshold,
        use_llm=use_llm,
    )

    # Phase 2: valuesets (depends on enriched values)
    logger.info("Enriching valuesets...")
    results["valuesets"] = enrich_valuesets(staging_dir)

    # Phase 3: schemas (last — may reference enriched elements/valuesets)
    logger.info("Enriching schemas...")
    results["schemas"] = enrich_schemas(
        staging_dir,
        cache_dir=None,
        onto_store=onto_store,
        onto_cache=onto_cache,
        model_name=model_name,
        threshold=threshold,
    )

    return results


def generate_curation_flags(
    staging_dir: Path,
    output_dir: Path | None = None,
) -> list:
    """Scan enriched entities and generate CurationFlags for ambiguous cases.

    Flags are generated for:
    - Elements/values/schemas with no ontology_annotations after enrichment (low_confidence)
    - Annotations where best score is borderline (0.7-0.95) and no LLM confirmed (ambiguous_match)
    - Multiple candidate annotations within 0.05 of each other (multiple_candidates)

    If output_dir is provided, flags are written to {output_dir}/curation-flags/.
    Returns list of CurationFlag objects.
    """
    from .curation import create_flag, write_flag
    from .models import FlagType

    flags = []

    for entity_type in ("elements", "values", "schemas"):
        entity_dir = staging_dir / entity_type
        if not entity_dir.exists():
            continue

        for f in sorted(entity_dir.glob("*.yaml")):
            data = safe_load_yaml(f)
            if data is None or "semantic" not in data:
                continue

            sem = data["semantic"]
            annotations = sem.get("ontology_annotations", [])

            if not annotations:
                # No annotations at all — flag as low_confidence
                prov = data.get("provenance", [{}])
                name = prov[0].get("name", f.stem) if prov else f.stem
                flag = create_flag(
                    entity_type=entity_type.rstrip("s"),  # elements → element
                    entity_ref=str(f.name),
                    flag_type=FlagType.low_confidence,
                    context={"reason": "no ontology annotations after enrichment", "name": name},
                )
                flags.append(flag)
                continue

            # Check for ambiguous matches (top score borderline, no LLM confirmation)
            top = annotations[0]
            top_score = top.get("score", 0)
            if 0.7 <= top_score < 0.95 and not top.get("llm_verification"):
                flag = create_flag(
                    entity_type=entity_type.rstrip("s"),
                    entity_ref=str(f.name),
                    flag_type=FlagType.ambiguous_match,
                    context={
                        "reason": f"borderline match (score={top_score:.3f}), no LLM verification",
                        "top_match": top.get("term_uri", ""),
                        "top_label": top.get("term_label", ""),
                        "top_score": top_score,
                    },
                )
                flags.append(flag)

            # Check for multiple close candidates
            if len(annotations) >= 2:
                scores = [a.get("score", 0) for a in annotations[:5]]
                if len(scores) >= 2 and (scores[0] - scores[1]) < 0.05:
                    flag = create_flag(
                        entity_type=entity_type.rstrip("s"),
                        entity_ref=str(f.name),
                        flag_type=FlagType.multiple_candidates,
                        context={
                            "reason": f"multiple close candidates (gap={scores[0] - scores[1]:.3f})",
                            "candidates": [
                                {"uri": a.get("term_uri"), "score": a.get("score")}
                                for a in annotations[:3]
                            ],
                        },
                    )
                    flags.append(flag)

    # Write flags to output directory if provided
    if output_dir and flags:
        for flag in flags:
            write_flag(output_dir, flag)
        logger.info("Generated %d curation flags", len(flags))

    return flags


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _load_ontology_embeddings(cache_dir: Path, model_name: str) -> EmbeddingStore | None:
    """Load ontology embeddings from vector index (024) or legacy cache."""
    cache_base = Path.home() / ".cache" / "undata"
    for candidate in [
        cache_base / "ontology-vectors.parquet",
        cache_dir / "ontology-vectors.parquet",
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
    # Use entity-type-specific parquet to avoid collision between elements/values/schemas
    parquet_path = elements_dir / "embeddings.parquet"
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
    use_llm: bool = False,
    element_desc: str = "",
    source_context: str = "",
    ontology_rdf_store=None,
) -> list[dict]:
    """Assign multiple ontology annotations via embedding similarity.

    Returns list of OntologyAnnotation-compatible dicts.
    Heuristic: threshold + gap cutoff + max cap.
    If use_llm=True, borderline matches (0.7-0.95) are verified via LLM.
    If ontology_rdf_store is provided, ancestors of the primary match are
    added as broadMatch annotations (multi-precision enrichment).
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
        ontology = _ontology_from_uri(uri)
        mapping_relation = _score_to_skos(score)
        match_level = (
            MatchLevel.element_match if is_value and score >= 0.9 else MatchLevel.concept_match
        )

        # LLM verification for borderline matches
        llm_result = None
        if use_llm and 0.7 <= score < 0.95 and element_desc:
            from .llm_enrich import verify_borderline_match

            llm_result = verify_borderline_match(
                element_desc=element_desc,
                ontology_term_label=label,
                ontology_term_uri=uri,
                ontology_name=ontology,
                embedding_score=score,
                source_context=source_context or None,
            )
            # If LLM rejects, skip this annotation
            if llm_result.get("decision") == "reject":
                logger.info("LLM rejected match: %s ↔ %s (score=%.3f)", element_desc, label, score)
                continue

        ann: dict = {
            "term_uri": uri,
            "term_label": label,
            "ontology": ontology,
            "mapping_relation": mapping_relation,
            "match_level": match_level.value,
            "score": round(score, 4),
            "model": model_name,
            "primary": len(annotations) == 0,
        }
        if llm_result and llm_result.get("error") is None:
            ann["llm_verification"] = llm_result
        annotations.append(ann)
        prev_score = score

    # Multi-precision: add broadMatch annotations from ontology hierarchy
    if ontology_rdf_store and annotations:
        primary_uri = annotations[0].get("term_uri", "")
        if primary_uri:
            try:
                ancestors = ontology_rdf_store.get_ancestors(primary_uri, max_depth=2)
                for anc_uri in ancestors[:3]:  # Limit to 3 broader terms
                    anc_info = onto_cache.get(anc_uri, {})
                    anc_label = anc_info.get("label", "")
                    if not anc_label:
                        # Try to look up label
                        term_data = ontology_rdf_store.lookup_term(anc_uri)
                        anc_label = term_data["label"] if term_data else ""
                    if anc_label:
                        annotations.append(
                            {
                                "term_uri": anc_uri,
                                "term_label": anc_label,
                                "ontology": _ontology_from_uri(anc_uri),
                                "mapping_relation": "skos:broadMatch",
                                "match_level": MatchLevel.concept_match.value,
                                "score": 0.0,  # Not from embedding
                                "model": "hierarchy",
                                "primary": False,
                            }
                        )
            except Exception:
                pass  # Hierarchy lookup is best-effort

    return annotations


def _score_to_skos(score: float) -> str:
    """Map cosine similarity to SKOS mapping relation."""
    if score >= 0.95:
        return "skos:exactMatch"
    if score >= 0.8:
        return "skos:closeMatch"
    if score >= 0.5:
        return "skos:relatedMatch"
    return "skos:noMatch"


def _ontology_from_uri(uri: str) -> str:
    """Extract ontology prefix from term URI."""
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
        if value.startswith("https://"):
            continue
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
            uri = f"{BASE_URI}/values/{f.stem}"
            if label:
                lookup[label.lower()] = uri
            for p in data.get("provenance", []):
                raw = p.get("raw_value", "")
                if raw:
                    lookup[raw.lower()] = uri
        except (yaml.YAMLError, OSError):
            continue
    return lookup
