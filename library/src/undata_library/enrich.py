"""Enrichment pipeline: in-place enrichment of staged registry entities.

Enrichment fills every field in SemanticIdentity that can be inferred:
- ontology_annotations: via embedding similarity to ontology terms
- value_domain: auto-populated from data_type
- unit / unit_uri: inferred from provenance description, resolved to QUDT
- pattern: inferred from description (ISO 8601, UUID, DOI, etc.)
- min_value / max_value: extracted from description
- response_options: resolved to ValueConcept URIs

All updates are in-place — no new entities are created.
Dependency order: elements + values → valuesets → schemas.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .storage.protocol import StorageBackend

import yaml

from .embeddings import EmbeddingStore, build_element_embeddings, build_ontology_embeddings
from .utils import BASE_URI, safe_load_yaml

logger = logging.getLogger(__name__)

# Module-level cache for ontology term metadata (loaded once from pyoxigraph)
_ONTO_CACHE_SINGLETON: dict[str, dict] | None = None


# ---------------------------------------------------------------------------
# In-place update (T023)
# ---------------------------------------------------------------------------


def _update_entity_in_place(
    filepath: Path,
    ontology_annotations: list[dict] | None = None,
    value_domain: str | None = None,
    description: str | None = None,
    unit: str | None = None,
    unit_uri: str | None = None,
    pattern: str | None = None,
    min_value: float | None = None,
    max_value: float | None = None,
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

    if unit is not None and not sem.get("unit"):
        sem["unit"] = unit
        changed = True

    if unit_uri is not None and not sem.get("unit_uri"):
        sem["unit_uri"] = unit_uri
        changed = True

    if pattern is not None and not sem.get("pattern"):
        sem["pattern"] = pattern
        changed = True

    if min_value is not None and sem.get("min_value") is None:
        sem["min_value"] = min_value
        changed = True

    if max_value is not None and sem.get("max_value") is None:
        sem["max_value"] = max_value
        changed = True

    if changed:
        filepath.write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    return changed


# ---------------------------------------------------------------------------
# Semantic field inference helpers
# ---------------------------------------------------------------------------

# Unit patterns found in descriptions — map regex to unit string
_UNIT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(?:in\s+)?years?\b", re.I), "years"),
    (re.compile(r"\b(?:in\s+)?months?\b", re.I), "months"),
    (re.compile(r"\b(?:in\s+)?days?\b", re.I), "days"),
    (re.compile(r"\b(?:in\s+)?hours?\b", re.I), "hours"),
    (re.compile(r"\b(?:in\s+)?minutes?\b", re.I), "minutes"),
    (re.compile(r"\b(?:in\s+)?seconds?\b", re.I), "seconds"),
    (re.compile(r"\b(?:in\s+)?milliseconds?\b", re.I), "milliseconds"),
    (re.compile(r"\b(?:in\s+)?microseconds?\b", re.I), "microseconds"),
    (re.compile(r"\bISO\s*8601\b", re.I), "ISO8601"),
    (re.compile(r"\b(?:in\s+)?(?:milli)?meters?\b", re.I), "meters"),
    (re.compile(r"\b(?:in\s+)?centimeters?\b", re.I), "centimeters"),
    (re.compile(r"\b(?:in\s+)?millimeters?\b", re.I), "millimeters"),
    (re.compile(r"\b(?:in\s+)?microns?\b", re.I), "micrometers"),
    (re.compile(r"\b(?:in\s+)?micrometers?\b", re.I), "micrometers"),
    (re.compile(r"\b(?:in\s+)?kilograms?\b", re.I), "kilograms"),
    (re.compile(r"\b(?:in\s+)?grams?\b", re.I), "grams"),
    (re.compile(r"\b(?:in\s+)?pounds?\b", re.I), "pounds"),
    (re.compile(r"\b(?:in\s+)?hertz\b|\bHz\b", re.I), "hertz"),
    (re.compile(r"\b(?:in\s+)?(?:kilo)?hertz\b|\bkHz\b", re.I), "kilohertz"),
    (re.compile(r"\b(?:in\s+)?tesla\b|\bT\b"), "tesla"),
    (re.compile(r"\b(?:in\s+)?volts?\b|\bV\b"), "volts"),
    (re.compile(r"\b(?:in\s+)?millivolts?\b|\bmV\b"), "millivolts"),
    (re.compile(r"\b(?:in\s+)?degrees?\b", re.I), "degrees"),
    (re.compile(r"\b(?:in\s+)?radians?\b", re.I), "radians"),
    (re.compile(r"\b(?:in\s+)?percent(?:age)?\b|\b%\b", re.I), "percent"),
]

# Patterns that indicate specific value formats
_FORMAT_PATTERNS: list[tuple[re.Pattern, str]] = [
    (
        re.compile(r"\bISO\s*8601\b", re.I),
        r"^P(\d+Y)?(\d+M)?(\d+D)?(T(\d+H)?(\d+M)?(\d+(\.\d+)?S)?)?$",
    ),
    (re.compile(r"\bRFC\s*3339\b|\bdatetime\b", re.I), r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"),
    (
        re.compile(r"\bUUID\b", re.I),
        r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$",
    ),
    (re.compile(r"\bDOI\b", re.I), r"^10\.\d{4,}"),
    (re.compile(r"\bORCID\b", re.I), r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$"),
]

# Numeric bound extraction
_MIN_PATTERN = re.compile(r"\b(?:min(?:imum)?|at\s+least|>=?)\s*(\d+(?:\.\d+)?)", re.I)
_MAX_PATTERN = re.compile(r"\b(?:max(?:imum)?|at\s+most|<=?|capped\s+at)\s*(\d+(?:\.\d+)?)", re.I)


def _infer_unit_from_description(description: str, name: str = "") -> str | None:
    """Infer unit from element description or name.

    ISO 8601 takes priority: if the description mentions ISO 8601, return
    "ISO8601" immediately — don't let incidental mentions of "years" or
    "days" in ISO 8601 examples trigger a time-unit match.
    """
    text = f"{name} {description}"

    # ISO 8601 takes priority over all time units
    if re.search(r"\bISO\s*8601\b", text, re.I):
        return "ISO8601"

    for pattern, unit in _UNIT_PATTERNS:
        # Skip the ISO8601 entry in _UNIT_PATTERNS (handled above)
        if unit == "ISO8601":
            continue
        if pattern.search(text):
            return unit
    return None


def _infer_pattern_from_description(description: str) -> str | None:
    """Infer regex pattern from description if it mentions a known format."""
    for pattern, regex in _FORMAT_PATTERNS:
        if pattern.search(description):
            return regex
    return None


def _extract_bounds(description: str) -> tuple[float | None, float | None]:
    """Extract min/max numeric bounds from description."""
    min_val = None
    max_val = None
    m = _MIN_PATTERN.search(description)
    if m:
        min_val = float(m.group(1))
    m = _MAX_PATTERN.search(description)
    if m:
        max_val = float(m.group(1))
    return min_val, max_val


def _resolve_unit_uri(unit_str: str) -> str | None:
    """Resolve a unit string to a QUDT URI if the unit_resolver is available."""
    try:
        from .unit_resolver import get_resolver

        resolver = get_resolver()
        result = resolver.resolve(unit_str)
        if result:
            return result.uri
    except Exception:
        pass
    return None


def _enrich_semantic_fields(
    data: dict,
) -> dict[str, object]:
    """Infer missing semantic fields from provenance descriptions.

    Returns a dict of field_name → value for fields that could be inferred.
    Only returns fields that are currently missing/None in the semantic block.
    """
    sem = data.get("semantic", {})
    prov_list = data.get("provenance", [])
    first_prov = prov_list[0] if prov_list and isinstance(prov_list[0], dict) else {}

    description = first_prov.get("description", "") or sem.get("description", "") or ""
    name = first_prov.get("name", "")
    updates: dict[str, object] = {}

    # Infer unit
    if not sem.get("unit") and description:
        unit = _infer_unit_from_description(description, name)
        if unit:
            updates["unit"] = unit
            # Try to resolve URI
            uri = _resolve_unit_uri(unit)
            if uri:
                updates["unit_uri"] = uri

    # Infer pattern
    if not sem.get("pattern") and description:
        pattern = _infer_pattern_from_description(description)
        if pattern:
            updates["pattern"] = pattern

    # Extract min/max bounds
    if description:
        min_val, max_val = _extract_bounds(description)
        if min_val is not None and sem.get("min_value") is None:
            updates["min_value"] = min_val
        if max_val is not None and sem.get("max_value") is None:
            updates["max_value"] = max_val

    return updates


# ---------------------------------------------------------------------------
# Element enrichment (T024)
# ---------------------------------------------------------------------------


def enrich_elements(
    staging_dir: Path | None = None,
    cache_dir: Path | None = None,
    onto_store: EmbeddingStore | None = None,
    onto_cache: dict[str, dict] | None = None,
    model_name: str = "all-MiniLM-L6-v2",
    threshold: float = 0.7,
    dry_run: bool = False,
    use_llm: bool = False,
    *,
    backend: StorageBackend | None = None,
) -> dict[str, int]:
    """Enrich staged elements in-place: assign ontology_annotations, populate value_domain.

    Works on staging_dir/elements/. No new files are created.
    If use_llm=True, the candidate threshold drops to 0.4 and borderline matches
    (0.4-0.7) are verified by LLM before assignment. Without LLM, only matches
    above threshold (0.7) are auto-assigned.

    Returns stats: {ontology_assigned, value_domain_set, values_resolved, unchanged, total}
    """
    if staging_dir is None and backend is not None and hasattr(backend, "base_dir"):
        staging_dir = backend.base_dir
    elements_dir = staging_dir / "elements"
    if not elements_dir.exists():
        return {
            "ontology_assigned": 0,
            "value_domain_set": 0,
            "values_resolved": 0,
            "unchanged": 0,
            "total": 0,
        }

    # If no YAML files, delegate to Parquet-native _enrich_batch
    yaml_files = sorted(elements_dir.glob("*.yaml"))
    if not yaml_files:
        batch_stats = _enrich_batch(
            staging_dir,
            "elements",
            model_name=model_name,
            threshold=threshold,
            onto_store=onto_store,
            onto_cache=onto_cache,
            use_llm=use_llm,
        )
        # Map batch stats keys to enrich_elements return format
        return {
            "ontology_assigned": batch_stats.get("ontology_assigned", 0),
            "value_domain_set": batch_stats.get("value_domain_set", 0),
            "values_resolved": batch_stats.get("values_resolved", 0),
            "unchanged": batch_stats.get("unchanged", 0),
            "total": batch_stats.get("total", 0),
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

    # Collect candidates for batch LLM verification
    _llm_candidates: list[
        tuple
    ] = []  # (filepath, elem_desc, term_label, term_defn, term_uri, annotations)

    stats = {
        "ontology_assigned": 0,
        "value_domain_set": 0,
        "values_resolved": 0,
        "unchanged": 0,
        "total": 0,
    }

    for f in yaml_files:
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

        # 1. Assign ontology_annotations via embedding similarity
        # Skip if element has curated (human-approved) annotations
        has_curated = bool(data.get("curated_annotations"))
        if (
            not sem.get("ontology_annotations")
            and not has_curated
            and onto_store is not None
            and elem_store is not None
        ):
            uri = f"{BASE_URI}/elements/{f.stem}"
            # Use lower threshold when LLM batch verification follows
            effective_threshold = 0.4 if use_llm else threshold
            annotations = _assign_ontology_annotations(
                uri,
                elem_store,
                onto_store,
                onto_cache,
                effective_threshold,
                model_name=model_name,
                use_llm=False,  # No per-entity LLM; batch below
            )

            if use_llm and annotations:
                # Collect for batch LLM verification
                prov = data.get("provenance", [{}])
                first_prov = prov[0] if prov and isinstance(prov[0], dict) else {}
                elem_desc = f"{first_prov.get('class', '')} {first_prov.get('name', '')}"
                desc_text = first_prov.get("description") or sem.get("description", "")
                if desc_text:
                    elem_desc = f"{elem_desc}: {desc_text}"
                top = annotations[0]
                top_score = top.get("score", 0)
                if top_score < 0.95:  # Only verify non-obvious matches
                    _llm_candidates.append(
                        (
                            str(f),
                            elem_desc.strip(),
                            top.get("term_label", ""),
                            onto_cache.get(top["term_uri"], {}).get("definition", ""),
                            top["term_uri"],
                            annotations,
                        )
                    )
                    continue  # Don't assign yet — wait for batch verification
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

        # 4. Infer missing semantic fields (unit, pattern, min/max) from description
        sem_updates = _enrich_semantic_fields(data)
        if sem_updates:
            stats["semantic_fields_inferred"] = stats.get("semantic_fields_inferred", 0) + len(
                sem_updates
            )

        if annotations or domain or sem_updates:
            if not dry_run:
                _update_entity_in_place(
                    f,
                    ontology_annotations=annotations,
                    value_domain=domain,
                    unit=sem_updates.get("unit"),
                    unit_uri=sem_updates.get("unit_uri"),
                    pattern=sem_updates.get("pattern"),
                    min_value=sem_updates.get("min_value"),
                    max_value=sem_updates.get("max_value"),
                )
        else:
            stats["unchanged"] += 1

    # Batch LLM verification for collected candidates
    if _llm_candidates and use_llm:
        from .llm_enrich import verify_batch

        pairs = [
            (elem_desc, term_label, term_defn, term_uri)
            for _, elem_desc, term_label, term_defn, term_uri, _ in _llm_candidates
        ]
        logger.info("Batch LLM verification: %d candidates", len(pairs))
        decisions = verify_batch(pairs)

        for (filepath, _, _, _, _, anns), decision in zip(_llm_candidates, decisions):
            if decision == "confirm":
                if not dry_run:
                    _update_entity_in_place(Path(filepath), ontology_annotations=anns)
                stats["ontology_assigned"] += 1
            # reject/uncertain → not assigned, will be flagged by curation

    return stats


# ---------------------------------------------------------------------------
# Value enrichment (T025)
# ---------------------------------------------------------------------------


def enrich_from_source_metadata(
    staging_dir: Path | None = None, *, backend: StorageBackend | None = None
) -> dict[str, int]:
    if staging_dir is None and backend is not None and hasattr(backend, "base_dir"):
        staging_dir = backend.base_dir
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
    staging_dir: Path | None = None,
    cache_dir: Path | None = None,
    onto_store: EmbeddingStore | None = None,
    onto_cache: dict[str, dict] | None = None,
    model_name: str = "all-MiniLM-L6-v2",
    threshold: float = 0.7,
    use_llm: bool = False,
    *,
    backend: StorageBackend | None = None,
) -> dict[str, int]:
    """Enrich staged values in-place: assign ontology_annotations with element_match for high scores.

    Returns stats: {ontology_assigned, unchanged, total}
    """
    if staging_dir is None and backend is not None and hasattr(backend, "base_dir"):
        staging_dir = backend.base_dir
    values_dir = staging_dir / "values"
    if not values_dir.exists():
        return {"ontology_assigned": 0, "unchanged": 0, "total": 0}

    # If no YAML files, delegate to Parquet-native _enrich_batch
    yaml_files = sorted(values_dir.glob("*.yaml"))
    if not yaml_files:
        return _enrich_batch(
            staging_dir,
            "values",
            model_name=model_name,
            threshold=threshold,
            onto_store=onto_store,
            onto_cache=onto_cache,
            use_llm=use_llm,
        )

    if onto_store is None and cache_dir is not None:
        onto_store = _load_ontology_embeddings(cache_dir, model_name)
    if onto_cache is None and cache_dir is not None:
        onto_cache = _load_ontology_cache(cache_dir)
    onto_cache = onto_cache or {}

    # Build value embeddings
    elem_store = _load_or_build_element_embeddings(values_dir, model_name)

    stats = {"ontology_assigned": 0, "unchanged": 0, "total": 0}

    for f in yaml_files:
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
    staging_dir: Path | None = None,
    cache_dir: Path | None = None,
    onto_store: EmbeddingStore | None = None,
    onto_cache: dict[str, dict] | None = None,
    model_name: str = "all-MiniLM-L6-v2",
    threshold: float = 0.7,
    *,
    backend: StorageBackend | None = None,
) -> dict[str, int]:
    """Enrich staged schemas in-place: assign ontology_annotations (concept_match).

    Returns stats: {ontology_assigned, unchanged, total}
    """
    if staging_dir is None and backend is not None and hasattr(backend, "base_dir"):
        staging_dir = backend.base_dir
    schemas_dir = staging_dir / "schemas"
    if not schemas_dir.exists():
        return {"ontology_assigned": 0, "unchanged": 0, "total": 0}

    # If no YAML files, delegate to Parquet-native _enrich_batch
    yaml_files = sorted(schemas_dir.glob("*.yaml"))
    if not yaml_files:
        return _enrich_batch(
            staging_dir,
            "schemas",
            model_name=model_name,
            threshold=threshold,
            onto_store=onto_store,
            onto_cache=onto_cache,
        )

    if onto_store is None and cache_dir is not None:
        onto_store = _load_ontology_embeddings(cache_dir, model_name)
    if onto_cache is None and cache_dir is not None:
        onto_cache = _load_ontology_cache(cache_dir)
    onto_cache = onto_cache or {}

    # Build schema embeddings
    elem_store = _load_or_build_element_embeddings(schemas_dir, model_name)

    stats = {"ontology_assigned": 0, "unchanged": 0, "total": 0}

    for f in yaml_files:
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
    staging_dir: Path | None = None,
    *,
    backend: StorageBackend | None = None,
) -> dict[str, int]:
    """Enrich staged valuesets in-place: derive ontology_annotations from enriched member values.

    This runs AFTER enrich_values(), so member values already have ontology_annotations.
    Valuesets inherit the most common ontology namespace from their members.

    Returns stats: {enriched, unchanged, total}
    """
    if staging_dir is None and backend is not None and hasattr(backend, "base_dir"):
        staging_dir = backend.base_dir
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
    staging_dir: Path | None = None,
    cache_dir: Path | None = None,
    onto_store: EmbeddingStore | None = None,
    onto_cache: dict[str, dict] | None = None,
    model_name: str = "all-MiniLM-L6-v2",
    threshold: float = 0.7,
    use_llm: bool = False,
    *,
    backend: StorageBackend | None = None,
) -> dict[str, dict]:
    """Orchestrate enrichment of all entity types in dependency order.

    Order: (0) source metadata  (1) elements + values  (2) valuesets  (3) schemas

    When use_llm=True, candidate threshold drops to 0.4 and borderline matches
    are verified by LLM. Without LLM, only matches above threshold are auto-assigned.

    Returns: {source_metadata: {...}, elements: {...}, values: {...}, valuesets: {...}, schemas: {...}}
    """
    if staging_dir is None and backend is not None and hasattr(backend, "base_dir"):
        staging_dir = backend.base_dir

    # Load shared resources once
    if onto_store is None:
        onto_store = _load_ontology_embeddings(cache_dir or staging_dir, model_name)
    if onto_cache is None:
        onto_cache = _load_ontology_cache(cache_dir or staging_dir)
    onto_cache = onto_cache or {}

    results: dict[str, dict] = {}

    # Phase 0: Pre-enrich from source metadata
    logger.info("Pre-enriching from source metadata...")
    results["source_metadata"] = enrich_from_source_metadata(staging_dir)

    # Batch enrichment: read all entities via iter_staged, embed, match, write back

    for entity_type in ("elements", "values", "schemas", "valuesets"):
        logger.info("Enriching %s (batch)...", entity_type)
        stats = _enrich_batch(
            staging_dir,
            entity_type,
            model_name=model_name,
            threshold=threshold,
            onto_store=onto_store,
            onto_cache=onto_cache,
            use_llm=use_llm,
        )
        results[entity_type] = stats
        logger.info(
            "  %s: %d annotated / %d total",
            entity_type,
            stats.get("ontology_assigned", 0),
            stats.get("total", 0),
        )

    return results


def _enrich_batch(
    staging_dir: Path,
    entity_type: str,
    model_name: str = "all-MiniLM-L6-v2",
    threshold: float = 0.7,
    onto_store: EmbeddingStore | None = None,
    onto_cache: dict | None = None,
    use_llm: bool = False,
) -> dict:
    """Enrich all entities of a type in batch — Parquet-native.

    1. Read all entities from staging (Parquet + YAML)
    2. Compute embeddings in one batch
    3. Build EmbeddingStore from entity embeddings
    4. Match each against ontology index
    5. Write enriched entities back to staging Parquet
    """
    import numpy as np

    from .embeddings import EmbeddingStore, compute_entity_embeddings
    from .staging import iter_staged, write_staged_batch

    onto_cache = onto_cache or {}
    stats = {
        "total": 0,
        "ontology_assigned": 0,
        "unchanged": 0,
        "embedded": 0,
        "value_domain_set": 0,
    }

    # 1. Read all entities
    entities = list(iter_staged(staging_dir, entity_type))
    if not entities:
        return stats
    stats["total"] = len(entities)

    # Valuesets: aggregate annotations from member values (no embedding needed)
    if entity_type == "valuesets":
        stats["ontology_assigned"] = _enrich_valuesets_batch(entities, staging_dir)
        # Write back
        source = _get_source(entities)
        write_staged_batch(staging_dir, entity_type, entities, source=source)
        return stats

    # 2. Compute embeddings in one batch
    logger.info("  Computing embeddings for %d %s...", len(entities), entity_type)
    entities = compute_entity_embeddings(entities, model_name=model_name)
    stats["embedded"] = sum(1 for e in entities if e.get("embedding"))

    # 3. Build EmbeddingStore from entity embeddings
    uris = []
    vectors = []
    for i, entity in enumerate(entities):
        emb = entity.get("embedding")
        if emb is not None:
            uri = f"{BASE_URI}/{entity_type}/{i}"
            uris.append(uri)
            vectors.append(np.array(emb, dtype=np.float32))

    elem_store = None
    if vectors:
        elem_store = EmbeddingStore(uri_col="uri")
        elem_store._uris = uris
        elem_store._vectors = np.stack(vectors)
        elem_store._model = model_name
        elem_store._uri_to_idx = {u: idx for idx, u in enumerate(uris)}

    # 4. Match each entity against ontology index + enrich semantic fields
    is_value = entity_type == "values"
    for i, entity in enumerate(entities):
        sem = entity.get("semantic", {})
        ontology_changed = False

        # Ontology annotation matching (skip if already enriched/curated)
        if not sem.get("ontology_annotations") and not entity.get("curated_annotations"):
            if onto_store is not None and elem_store is not None:
                uri = f"{BASE_URI}/{entity_type}/{i}"
                prov = entity.get("provenance", [])
                first_prov = prov[0] if prov and isinstance(prov[0], dict) else {}
                element_desc = f"{first_prov.get('name', '')} {sem.get('description', '')}".strip()

                annotations = _assign_ontology_annotations(
                    uri,
                    elem_store,
                    onto_store,
                    onto_cache,
                    threshold,
                    is_value=is_value,
                    model_name=model_name,
                    element_desc=element_desc,
                )

                if annotations:
                    sem["ontology_annotations"] = annotations
                    entity["ontology_annotations"] = annotations
                    stats["ontology_assigned"] += 1
                    ontology_changed = True

        # Enrich semantic fields (unit, value_domain inference)
        _enrich_semantic_fields(entity)

        # Auto-populate value_domain from data_type
        if not sem.get("value_domain"):
            domain = _populate_value_domain(sem)
            if domain:
                sem["value_domain"] = domain
                stats["value_domain_set"] += 1
                ontology_changed = True

        if not ontology_changed:
            stats["unchanged"] += 1

        entity["semantic"] = sem

    # 5. Write enriched entities back to staging Parquet
    # Remove old parquet files first — we read ALL entities above, so this is a full replace
    from .storage.parquet_store import ParquetStore

    old_files = ParquetStore(staging_dir)._all_parquet_files(entity_type)
    for old_f in old_files:
        old_f.unlink(missing_ok=True)

    source = _get_source(entities)
    write_staged_batch(staging_dir, entity_type, entities, source=source)

    return stats


def _get_source(entities: list[dict]) -> str:
    """Extract source name from entity provenance."""
    if entities and entities[0].get("provenance"):
        prov = entities[0]["provenance"]
        if prov and isinstance(prov[0], dict):
            return prov[0].get("source", "enriched")
    return "enriched"


def _enrich_valuesets_batch(entities: list[dict], staging_dir: Path) -> int:
    """Aggregate ontology annotations from member values into valuesets."""
    enriched = 0
    # Build value label → annotations lookup from enriched values
    val_annotations: dict[str, list] = {}
    from .staging import iter_staged

    for val in iter_staged(staging_dir, "values"):
        sem = val.get("semantic", {})
        label = sem.get("label", "")
        anns = sem.get("ontology_annotations", [])
        if label and anns:
            val_annotations[label] = anns

    for entity in entities:
        sem = entity.get("semantic", {})
        if sem.get("ontology_annotations"):
            continue  # Already enriched
        members = sem.get("members", [])
        if not members:
            continue
        # Collect annotations from member values
        collected = []
        for member in members:
            if member in val_annotations:
                collected.extend(val_annotations[member])
        if collected:
            sem["ontology_annotations"] = collected[:5]  # Cap at 5
            entity["semantic"] = sem
            enriched += 1
    return enriched


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

    # Build set of existing (entity_ref, flag_type) to deduplicate
    existing_flags: set[tuple[str, str]] = set()
    if output_dir:
        flags_dir = output_dir / "curation-flags"
        if flags_dir.exists():
            for ff in flags_dir.glob("*.yaml"):
                fdata = safe_load_yaml(ff)
                if fdata:
                    existing_flags.add((fdata.get("entity_ref", ""), fdata.get("flag_type", "")))

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
                # No annotations — this is the default state for most entities.
                # Don't flag every unannotated entity (that would be 90%+ of all entities).
                # Only flag if the entity had enrichment candidates that were below threshold.
                continue

            # Check for ambiguous matches (top score borderline, no LLM confirmation)
            top = annotations[0]
            top_score = top.get("score", 0)
            if 0.7 <= top_score < 0.95 and not top.get("llm_verification"):
                if (f.stem, FlagType.ambiguous_match.value) not in existing_flags:
                    flag = create_flag(
                        entity_type=entity_type.rstrip("s"),
                        entity_ref=f.stem,
                        flag_type=FlagType.ambiguous_match,
                        context={
                            "reason": f"borderline match (score={top_score:.3f}), no LLM verification",
                            "top_match": top.get("term_uri", ""),
                            "top_label": top.get("term_label", ""),
                            "top_score": top_score,
                        },
                    )
                    flags.append(flag)
                    existing_flags.add((f.stem, FlagType.ambiguous_match.value))

            # Check for multiple close candidates
            if len(annotations) >= 2:
                scores = [a.get("score", 0) for a in annotations[:5]]
                if len(scores) >= 2 and (scores[0] - scores[1]) < 0.05:
                    if (f.stem, FlagType.multiple_candidates.value) not in existing_flags:
                        flag = create_flag(
                            entity_type=entity_type.rstrip("s"),
                            entity_ref=f.stem,
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
                        existing_flags.add((f.stem, FlagType.multiple_candidates.value))

    # Write flags to output directory if provided
    if output_dir and flags:
        for flag in flags:
            write_flag(output_dir, flag)
        logger.info("Generated %d curation flags", len(flags))

    return flags


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------


def _get_ontology_store_checksum() -> str | None:
    """Get a combined checksum of all loaded ontologies for staleness detection."""
    import hashlib

    try:
        from .ontology_store import OntologyStore

        store_path = Path.home() / ".cache" / "undata" / "ontology-store"
        if not store_path.exists():
            return None
        store = OntologyStore(store_path)
        loaded = store.list_loaded()
        checksums = sorted(e.get("checksum", "") for e in loaded if e.get("checksum"))
        if not checksums:
            return None
        return hashlib.sha256("|".join(checksums).encode()).hexdigest()[:16]
    except Exception:
        return None


def _load_ontology_embeddings(cache_dir: Path, model_name: str) -> EmbeddingStore | None:
    """Load ontology embeddings from vector index, with staleness check.

    If the ontology store checksum differs from the index checksum, auto-rebuild.
    """
    cache_base = Path.home() / ".cache" / "undata"
    current_checksum = _get_ontology_store_checksum()
    checksum_file = cache_base / "ontology-vectors.checksum"
    stored_checksum = checksum_file.read_text().strip() if checksum_file.exists() else None

    # Check staleness
    is_stale = current_checksum and stored_checksum and current_checksum != stored_checksum
    if is_stale:
        logger.info(
            "Ontology vector index is stale (store=%s, index=%s), will rebuild",
            current_checksum,
            stored_checksum,
        )

    if not is_stale:
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

    # If stale, rebuild from cache; if missing, warn and skip
    if not is_stale:
        logger.warning(
            "No ontology embedding index found. Run 'undata-library embed --include-ontology' "
            "to build the ontology vector index before enrichment."
        )
        return None

    # Rebuild stale index
    try:
        store = build_ontology_embeddings(cache_dir, model_name=model_name)
        if store.size > 0:
            save_path = cache_base / "ontology-vectors.parquet"
            save_path.parent.mkdir(parents=True, exist_ok=True)
            store.save(save_path, model_name=model_name)
            # Store checksum for future staleness detection
            if current_checksum:
                checksum_file.write_text(current_checksum)
            logger.info("Built ontology embeddings: %d terms", store.size)
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
    """Load ontology term metadata — tries pyoxigraph store first, then legacy YAML.

    Returns dict[term_uri → {label, synonyms, definition, deprecated, parents}].
    """
    cache: dict[str, dict] = {}

    # Try pyoxigraph store (primary — has all terms with labels/synonyms)
    # Use a module-level cache to avoid re-loading 268K terms on every call
    global _ONTO_CACHE_SINGLETON
    if _ONTO_CACHE_SINGLETON is not None:
        return _ONTO_CACHE_SINGLETON

    store_path = Path.home() / ".cache" / "undata" / "ontology-store"
    if store_path.exists():
        try:
            from .ontology_store import OntologyStore

            store = OntologyStore(store_path)
            for uri, label, synonyms in store.all_terms():
                cache[uri] = {
                    "label": label,
                    "synonyms": synonyms,
                    "deprecated": False,
                }
            if cache:
                logger.info("Loaded %d terms from ontology store", len(cache))
                _ONTO_CACHE_SINGLETON = cache
                return cache
        except Exception as exc:
            logger.warning("Failed to load from ontology store: %s", exc)

    # Fallback: legacy YAML cache files
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

        # LLM verification for borderline matches (below 0.95 auto-assign threshold)
        llm_result = None
        if use_llm and score < 0.95 and element_desc:
            from .llm_enrich import verify_borderline_match

            # Get term definition and synonyms from onto_cache for LLM context
            term_defn = term_info.get("definition") or term_info.get("description")
            term_syns = term_info.get("synonyms", [])

            llm_result = verify_borderline_match(
                element_desc=element_desc,
                ontology_term_label=label,
                ontology_term_uri=uri,
                ontology_name=ontology,
                embedding_score=score,
                source_context=source_context or None,
                ontology_term_definition=term_defn,
                ontology_term_synonyms=term_syns if term_syns else None,
            )
            # If LLM rejects, skip this annotation
            if llm_result.get("decision") == "reject":
                logger.info("LLM rejected match: %s ↔ %s (score=%.3f)", element_desc, label, score)
                continue

        # Build reasoning text
        term_defn = term_info.get("definition") or term_info.get("description") or ""
        if llm_result and llm_result.get("justification"):
            reasoning = str(llm_result["justification"])
            sim_method = "llm_reasoning"
        else:
            reasoning = (
                f"Cosine embedding similarity {score:.3f} between "
                f"element '{element_desc[:80]}' and ontology term '{label}'"
                f"{(' — ' + term_defn[:120]) if term_defn else ''}. "
                f"Relation: {mapping_relation}."
            )
            sim_method = "cosine_embedding"

        ann: dict = {
            "term_uri": uri,
            "term_label": label,
            "ontology": ontology,
            "mapping_relation": mapping_relation,
            "match_level": match_level.value,
            "score": round(score, 4),
            "model": model_name,
            "primary": len(annotations) == 0,
            "evidence": {
                "similarity_score": round(score, 4),
                "similarity_method": sim_method,
                "source_text": element_desc[:500] if element_desc else element_uri,
                "target_term_uri": uri,
                "target_term_label": label,
                "target_term_definition": term_defn[:500] if term_defn else None,
                "uri_verified": False,
                "reasoning": reasoning,
            },
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

    annotations = _prefer_species_over_genus(annotations)

    return annotations


def _prefer_species_over_genus(annotations: list[dict]) -> list[dict]:
    """Remove genus-level NCBITaxon matches when a more precise species-level match exists.

    For example, if both "Mus" (genus, NCBITaxon_10088) and "Mus musculus"
    (species, NCBITaxon_10090) are present, the genus-level annotation is
    removed because the species-level one is more informative.

    The heuristic: among NCBITaxon annotations, if one term's label is a prefix
    of another (e.g. "Mus" is a prefix of "Mus musculus"), the shorter/less-specific
    one is redundant and removed.
    """
    if not annotations:
        return annotations

    # Collect NCBITaxon annotations with their indices
    taxon_entries: list[tuple[int, dict]] = []
    for i, ann in enumerate(annotations):
        uri = ann.get("term_uri", "")
        if "NCBITaxon" in uri or "ncbitaxon" in uri.lower():
            taxon_entries.append((i, ann))

    if len(taxon_entries) < 2:
        return annotations

    # Find genus-level URIs to remove: a taxon annotation is genus-level if
    # another taxon annotation's label starts with it (i.e., it's a prefix).
    indices_to_remove: set[int] = set()
    for i, ann_a in taxon_entries:
        label_a = (ann_a.get("term_label") or "").strip().lower()
        if not label_a:
            continue
        for j, ann_b in taxon_entries:
            if i == j:
                continue
            label_b = (ann_b.get("term_label") or "").strip().lower()
            if not label_b:
                continue
            # If label_a is a strict prefix of label_b, label_a is the genus
            if label_b.startswith(label_a + " ") and len(label_b) > len(label_a):
                indices_to_remove.add(i)
                break

    if not indices_to_remove:
        return annotations

    return [ann for idx, ann in enumerate(annotations) if idx not in indices_to_remove]


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
