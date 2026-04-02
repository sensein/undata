"""Transform generation engine — detect patterns and create typed unidirectional transforms.

Upper-triangular cross-walk: each pair compared once (A→B only, not B→A).
Filters: no array→singleton transforms (unless structural_type annotated).
Only generates transforms between singleton elements sharing an ontology URI.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .storage.protocol import StorageBackend
import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .utils import BASE_URI

from .hashing import canonical_json, compute_sha256, generate_short_key
from .models import FunctionSpec, MappingFunctionType, ProvenanceEntry, TransformRecord

logger = logging.getLogger(__name__)

# Known unit conversion factors: (unit_a, unit_b) → factor (a * factor = b)
_UNIT_CONVERSIONS: dict[tuple[str, str], float] = {
    ("year", "month"): 12.0,
    ("month", "year"): 1.0 / 12.0,
    ("meter", "centimeter"): 100.0,
    ("centimeter", "meter"): 0.01,
    ("kilogram", "gram"): 1000.0,
    ("gram", "kilogram"): 0.001,
    ("second", "millisecond"): 1000.0,
    ("millisecond", "second"): 0.001,
}


def generate_transforms(
    elements_dir: Path | None = None,
    library_path: Path | None = None,
    threshold: float = 0.5,
    *,
    backend: StorageBackend | None = None,
    name_similarity_threshold: float = 0.8,
) -> dict[str, int]:
    """Generate transforms between cross-source elements via three strategies:

    1. Shared ontology URI (original)
    2. Name-based matching (case-insensitive provenance name across sources)
    3. Embedding similarity (cosine > name_similarity_threshold across sources)

    Returns stats: {pairs_evaluated, transforms_created, patterns: {identity, unit_conversion, ...}}
    """
    if elements_dir is None and backend is not None and hasattr(backend, "base_dir"):
        elements_dir = backend.base_dir / "elements"
        library_path = library_path or backend.base_dir
    transforms_dir = library_path / "transforms"
    transforms_dir.mkdir(parents=True, exist_ok=True)

    # Load all elements with their provenance source
    all_elements: list[tuple[str, dict, str]] = []  # (uri, data, source)
    by_onto: dict[str, list[tuple[str, dict]]] = {}
    by_name: dict[str, list[tuple[str, dict, str]]] = {}  # name.lower() → [(uri, data, source)]

    for f in sorted(elements_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "semantic" not in data:
                continue
        except (yaml.YAMLError, OSError):
            continue

        uri = f"{BASE_URI}/elements/{f.stem}"
        prov = data.get("provenance", [{}])
        source = prov[0].get("source", "") if prov else ""
        prov_name = prov[0].get("name", "") if prov else ""
        all_elements.append((uri, data, source))

        # Group by provenance name (case-insensitive) for name-based matching
        if prov_name:
            by_name.setdefault(prov_name.lower(), []).append((uri, data, source))

        # Group by primary annotation URI
        annotations = data["semantic"].get("ontology_annotations", [])
        onto = None
        if annotations:
            for ann in annotations:
                if isinstance(ann, dict) and ann.get("primary"):
                    onto = ann.get("term_uri")
                    break
            if not onto and annotations and isinstance(annotations[0], dict):
                onto = annotations[0].get("term_uri")
        if onto:
            by_onto.setdefault(onto, []).append((uri, data))

    stats = {
        "pairs_evaluated": 0,
        "transforms_created": 0,
        "patterns": {t.value: 0 for t in MappingFunctionType},
    }

    existing = {f.stem for f in transforms_dir.glob("*.yaml")}
    now_iso = datetime.now(timezone.utc).isoformat()
    seen_pairs: set[tuple[str, str]] = set()  # avoid duplicate transforms

    def _try_create_transform(uri_a: str, data_a: dict, uri_b: str, data_b: dict) -> bool:
        """Evaluate a pair and create transform if appropriate. Returns True if created."""
        pair_key = (min(uri_a, uri_b), max(uri_a, uri_b))
        if pair_key in seen_pairs:
            return False
        seen_pairs.add(pair_key)
        stats["pairs_evaluated"] += 1

        sem_a = data_a["semantic"]
        sem_b = data_b["semantic"]

        # Skip same-hash pairs
        can_a = canonical_json(sem_a)
        can_b = canonical_json(sem_b)
        if compute_sha256(can_a) == compute_sha256(can_b):
            return False

        # Skip array-typed unless structural_type
        type_a = sem_a.get("data_type", "string")
        type_b = sem_b.get("data_type", "string")
        if type_a == "array" and not sem_a.get("structural_type"):
            return False
        if type_b == "array" and not sem_b.get("structural_type"):
            return False

        func_spec = _detect_pattern(sem_a, sem_b)
        if func_spec is None:
            return False

        _write_transform(uri_a, uri_b, func_spec, transforms_dir, existing, now_iso)
        stats["transforms_created"] += 1
        stats["patterns"][func_spec.function_type.value] += 1
        return True

    # Strategy 1: Shared ontology URI (original logic)
    for onto_term, elements in by_onto.items():
        n = len(elements)
        for i in range(n):
            uri_a, data_a = elements[i]
            for j in range(i + 1, n):
                uri_b, data_b = elements[j]
                _try_create_transform(uri_a, data_a, uri_b, data_b)

    # Strategy 2: Name-based matching (cross-source only)
    for name_key, elements in by_name.items():
        if len(elements) < 2:
            continue
        # Only match cross-source pairs
        n = len(elements)
        for i in range(n):
            uri_a, data_a, src_a = elements[i]
            for j in range(i + 1, n):
                uri_b, data_b, src_b = elements[j]
                if src_a == src_b:
                    continue  # same source — skip
                _try_create_transform(uri_a, data_a, uri_b, data_b)

    # Strategy 3: Embedding similarity matching (cross-source, above threshold)
    if name_similarity_threshold < 1.0:
        try:
            from .embeddings import EmbeddingStore, cosine_similarity, DEFAULT_MODEL, _encode_texts

            # Build element embeddings on-the-fly from descriptions
            uri_to_data: dict[str, dict] = {}
            uri_to_source: dict[str, str] = {}
            texts: list[str] = []
            uris: list[str] = []

            for uri, data, source in all_elements:
                prov = data.get("provenance", [{}])
                name = prov[0].get("name", "") if prov else ""
                desc = data["semantic"].get("description", "")
                text = f"{name}: {desc}" if desc else name
                if not text:
                    continue
                uri_to_data[uri] = data
                uri_to_source[uri] = source
                uris.append(uri)
                texts.append(text)

            if len(texts) > 1:
                vectors = _encode_texts(texts, DEFAULT_MODEL)
                if vectors is not None:
                    import numpy as np

                    # Compare cross-source pairs above threshold
                    # Use batched dot product for efficiency
                    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
                    norms[norms == 0] = 1e-10
                    normed = vectors / norms

                    embed_created = 0
                    for i in range(len(uris)):
                        if embed_created > 500:  # cap to avoid O(n²) explosion
                            break
                        src_i = uri_to_source[uris[i]]
                        # Compute similarities for this element against all later elements
                        sims = normed[i] @ normed[i + 1:].T
                        for j_offset in range(len(sims)):
                            if sims[j_offset] < name_similarity_threshold:
                                continue
                            j = i + 1 + j_offset
                            if uri_to_source[uris[j]] == src_i:
                                continue  # same source
                            # Look up data for this pair from uri_to_data
                            data_i = uri_to_data[uris[i]]
                            data_j = uri_to_data[uris[j]]
                            if _try_create_transform(uris[i], data_i, uris[j], data_j):
                                embed_created += 1

                    logger.info("Embedding similarity: %d additional transforms", embed_created)
        except ImportError:
            logger.debug("sentence-transformers not available, skipping embedding similarity")
        except Exception as e:
            logger.warning("Embedding similarity matching failed: %s", e)

    logger.info(
        "Transforms generated: %d (ontology + name + embedding) from %d pairs",
        stats["transforms_created"],
        stats["pairs_evaluated"],
    )
    return stats


def _detect_pattern(sem_a: dict, sem_b: dict) -> FunctionSpec | None:
    """Detect the conversion pattern between two semantic identities."""
    type_a = sem_a.get("data_type", "string")
    type_b = sem_b.get("data_type", "string")
    unit_a = sem_a.get("unit")
    unit_b = sem_b.get("unit")

    # Value mapping: overlapping enums/response_options (check before identity)
    opts_a = _extract_values(sem_a)
    opts_b = _extract_values(sem_b)
    if opts_a and opts_b and set(opts_a) != set(opts_b):
        shared = set(opts_a) & set(opts_b)
        total = set(opts_a) | set(opts_b)
        if total and len(shared) / len(total) > 0.3:
            lookup = {v: v for v in sorted(shared)}
            return FunctionSpec(
                function_type=MappingFunctionType.value_mapping,
                input_type=type_a,
                output_type=type_b,
                expression=json.dumps(lookup),
                expression_type="lookup_table",
                parameters={"shared_count": len(shared), "total_count": len(total)},
            )

    # Identity: same type, same unit, same value set
    if type_a == type_b and unit_a == unit_b:
        return FunctionSpec(
            function_type=MappingFunctionType.identity,
            input_type=type_a,
            output_type=type_b,
            expression_type="none",
        )

    # Unit conversion: same type, different unit
    if type_a == type_b and unit_a and unit_b:
        factor = _UNIT_CONVERSIONS.get((unit_a, unit_b))
        if factor is not None:
            return FunctionSpec(
                function_type=MappingFunctionType.unit_conversion,
                input_type=type_a,
                output_type=type_b,
                expression=f"value * {factor}",
                expression_type="arithmetic",
                parameters={"factor": factor, "unit_from": unit_a, "unit_to": unit_b},
            )

    # Type conversion: float ↔ string (ISO8601 duration)
    if _is_numeric(type_a) and type_b == "string" and _is_iso8601_context(sem_b):
        return FunctionSpec(
            function_type=MappingFunctionType.type_conversion,
            input_type=type_a,
            output_type=type_b,
            expression="iso8601_duration_from_years",
            expression_type="named_function",
        )
    if type_a == "string" and _is_numeric(type_b) and _is_iso8601_context(sem_a):
        return FunctionSpec(
            function_type=MappingFunctionType.type_conversion,
            input_type=type_a,
            output_type=type_b,
            expression="years_from_iso8601_duration",
            expression_type="named_function",
        )

    # Structural: object ↔ primitive
    if (type_a == "object" and type_b != "object") or (type_a != "object" and type_b == "object"):
        return FunctionSpec(
            function_type=MappingFunctionType.structural,
            input_type=type_a,
            output_type=type_b,
            expression_type="template",
        )

    # Different types, unknown relation
    if type_a != type_b:
        return FunctionSpec(
            function_type=MappingFunctionType.unknown,
            input_type=type_a,
            output_type=type_b,
            expression_type="none",
        )

    return None


def _reverse_function(func: FunctionSpec) -> FunctionSpec:
    """Create the reverse function spec (B → A)."""
    if func.function_type == MappingFunctionType.identity:
        return FunctionSpec(
            function_type=MappingFunctionType.identity,
            input_type=func.output_type,
            output_type=func.input_type,
            expression_type="none",
        )

    if func.function_type == MappingFunctionType.unit_conversion and func.parameters:
        factor = func.parameters.get("factor", 1.0)
        reverse_factor = 1.0 / factor if factor != 0 else 0
        return FunctionSpec(
            function_type=MappingFunctionType.unit_conversion,
            input_type=func.output_type,
            output_type=func.input_type,
            expression=f"value * {reverse_factor}",
            expression_type="arithmetic",
            parameters={
                "factor": reverse_factor,
                "unit_from": func.parameters.get("unit_to"),
                "unit_to": func.parameters.get("unit_from"),
            },
        )

    if func.function_type == MappingFunctionType.type_conversion:
        # Swap named function
        reverse_expr = None
        if func.expression == "iso8601_duration_from_years":
            reverse_expr = "years_from_iso8601_duration"
        elif func.expression == "years_from_iso8601_duration":
            reverse_expr = "iso8601_duration_from_years"
        return FunctionSpec(
            function_type=MappingFunctionType.type_conversion,
            input_type=func.output_type,
            output_type=func.input_type,
            expression=reverse_expr,
            expression_type=func.expression_type,
        )

    # For value_mapping, structural, unknown — swap types, keep same expression
    return FunctionSpec(
        function_type=func.function_type,
        input_type=func.output_type,
        output_type=func.input_type,
        expression=func.expression,
        expression_type=func.expression_type,
        parameters=func.parameters,
    )


def _write_transform(
    source_uri: str,
    target_uri: str,
    func_spec: FunctionSpec,
    transforms_dir: Path,
    existing: set[str],
    now_iso: str,
) -> None:
    """Write a single transform YAML file."""
    # Content-addressed hash from source + target + function
    identity = {
        "source_element": source_uri,
        "target_element": target_uri,
        "function": func_spec.model_dump(exclude_none=True),
    }
    canonical = canonical_json(identity)
    sha = compute_sha256(canonical)
    key = generate_short_key(sha)

    # Derive names for filename
    src_name = source_uri.rsplit("/", 1)[-1].rsplit("_", 1)[0]
    tgt_name = target_uri.rsplit("/", 1)[-1].rsplit("_", 1)[0]
    filename = f"{src_name}_to_{tgt_name}_{key}"

    if filename in existing:
        return

    record = TransformRecord(
        source_element=source_uri,
        target_element=target_uri,
        function=func_spec,
        provenance=[
            ProvenanceEntry(
                source="auto",
                **{"class": ""},
                name="",
                generated_at=now_iso,
                attributed_to="urn:undata:transform-pipeline",
                activity="transform",
            ),
        ],
    )

    data = record.model_dump(mode="json", exclude_none=True, by_alias=True)
    data["sha256"] = sha

    (transforms_dir / f"{filename}.yaml").write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    existing.add(filename)


def _is_numeric(dt: str) -> bool:
    return dt in ("integer", "float")


def _is_iso8601_context(sem: dict) -> bool:
    """Check if the element has ISO8601 duration context."""
    unit = sem.get("unit", "")
    if unit and "iso8601" in unit.lower():
        return True
    # Check if any hint of ISO8601 in the semantic
    for key in ("unit", "value_domain"):
        val = sem.get(key, "")
        if val and "iso" in str(val).lower():
            return True
    return False


def _extract_values(sem: dict) -> list[str]:
    """Extract enum/response_option values for comparison."""
    opts = sem.get("response_options", [])
    if opts:
        return [o.get("value", "") for o in opts if isinstance(o, dict)]
    constraints = sem.get("constraints", {})
    if constraints and constraints.get("allowed_values"):
        return constraints["allowed_values"]
    return []


def flag_unknown_transforms(
    transforms_dir: Path,
    output_dir: Path | None = None,
) -> list:
    """Scan transforms and create CurationFlags for unknown function types.

    Returns list of CurationFlag objects.
    """
    from .curation import create_flag, write_flag
    from .models import FlagType
    from .utils import safe_load_yaml

    flags = []
    if not transforms_dir.exists():
        return flags

    for f in sorted(transforms_dir.glob("*.yaml")):
        data = safe_load_yaml(f)
        if data is None:
            continue

        func = data.get("function", {})
        if func.get("function_type") == "unknown":
            flag = create_flag(
                entity_type="transform",
                entity_ref=str(f.name),
                flag_type=FlagType.unknown_transform,
                context={
                    "reason": "unknown conversion function type",
                    "source_element": data.get("source_element", ""),
                    "target_element": data.get("target_element", ""),
                    "input_type": func.get("input_type", ""),
                    "output_type": func.get("output_type", ""),
                },
            )
            flags.append(flag)

    if output_dir and flags:
        for flag in flags:
            write_flag(output_dir, flag)
        logger.info("Flagged %d unknown transforms", len(flags))

    return flags
