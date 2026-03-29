"""Ingestion pipeline: raw schemas → content-addressed v2 YAML files."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .storage.protocol import StorageBackend

import yaml

from .utils import BASE_URI, safe_load_yaml, sanitize_filename

from .hashing import (
    build_value_uri,
    canonical_json,
    compute_sha256,
    generate_short_key,
)
from .models import (
    ElementRecord,
    HashRegistry,
    HashRegistryEntry,
    ProvenanceEntry,
    ResponseOption,
    SemanticIdentity,
    ValueConcept,
    ValueSemanticIdentity,
)


def ingest_source(
    source_name: str,
    schema_path: Path | None,
    library_path: Path | None = None,
    *,
    backend: "StorageBackend | None" = None,
) -> dict[str, int]:
    """Ingest elements from a single source into the library.

    Accepts either library_path (Path) or backend (StorageBackend).
    If backend is provided and has a base_dir attribute, uses that as library_path.

    Returns stats: {created, merged, total}.
    """
    if library_path is None and backend is not None and hasattr(backend, "base_dir"):
        library_path = backend.base_dir
    elif library_path is None and backend is None:
        raise ValueError("Either library_path or backend must be provided")
    from datetime import datetime, timezone

    # Load extractor — returns (attribute_pairs, all_entities)
    pairs, all_entities = _extract(source_name, schema_path)

    # Auto-populate PROV-O fields on all provenance entries
    now_iso = datetime.now(timezone.utc).isoformat()
    for _sem, prov in pairs:
        if prov.generated_at is None:
            prov.generated_at = now_iso
        if prov.attributed_to is None:
            prov.attributed_to = "urn:undata:ingestion-pipeline"
        if prov.activity is None:
            prov.activity = "ingestion"

    # Note: ontology annotations are now applied post-ingestion via
    # `undata-library annotate` CLI command, not during ingestion.
    # This keeps ingestion pure (source data only) and tracks annotations
    # as separate PROV-O curation events.

    # Route all entity types to their correct directories
    import uuid

    from .models import EntityType

    stats_by_type: dict[str, int] = {
        "elements": 0,
        "schemas": 0,
        "values": 0,
        "valuesets": 0,
    }

    # Map entity types to directory names
    type_to_dir = {
        EntityType.ATTRIBUTE: "elements",
        EntityType.CLASS: "schemas",
        EntityType.ENUM_VALUE: "values",
        EntityType.VALUESET: "valuesets",
    }

    # Create all directories
    for dirname in type_to_dir.values():
        (library_path / dirname).mkdir(parents=True, exist_ok=True)

    # Dedup by (entity_type, source, class, name)
    seen_keys: set[tuple[str, str, str, str]] = set()
    created = 0
    merged = 0

    # Write ATTRIBUTE entities from pairs (legacy path — these have SemanticIdentity)
    for sem, prov in pairs:
        dedup_key = ("attribute", prov.source, prov.class_, prov.name)
        if dedup_key in seen_keys:
            merged += 1
            continue
        seen_keys.add(dedup_key)

        record = ElementRecord(semantic=sem, provenance=[prov])
        filepath = library_path / "elements" / f"{uuid.uuid4()}.yaml"
        _write_element(filepath, record)
        created += 1
        stats_by_type["elements"] += 1

    # Write CLASS, ENUM_VALUE, VALUESET entities from all_entities
    for entity in all_entities:
        etype = entity.entity_type
        dirname = type_to_dir.get(etype)
        if dirname is None or dirname == "elements":
            continue  # Elements handled above via pairs

        prov = entity.provenance if isinstance(entity.provenance, dict) else {}
        dedup_key = (
            etype.value,
            prov.get("source", ""),
            prov.get("class", ""),
            prov.get("name", ""),
        )
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)

        data = {
            "semantic": entity.semantic if isinstance(entity.semantic, dict) else {},
            "provenance": [prov],
        }
        filepath = library_path / dirname / f"{uuid.uuid4()}.yaml"
        filepath.write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        stats_by_type[dirname] += 1

    # Legacy: also extract values from response_options on elements
    registry_path = library_path / "hash-registry.yaml"
    registry = _load_registry(registry_path)
    value_stats = _extract_values(source_name, pairs, library_path, registry)
    stats_by_type["values"] += value_stats.get("created", 0)

    # Resolve response_option values to ValueConcept URIs
    _resolve_response_option_uris(library_path)

    return {
        "created": created,
        "merged": merged,
        "total": created + merged,
        "schemas_created": stats_by_type["schemas"],
        "values_created": stats_by_type["values"],
        "valuesets_created": stats_by_type["valuesets"],
        "mappings_created": 0,
    }


def _load_value_mappings(library_path: Path) -> dict[str, dict]:
    """Load value-mappings.yaml: raw_value → {label}."""
    mappings_path = library_path / "value-mappings.yaml"
    if not mappings_path.exists():
        return {}
    data = safe_load_yaml(mappings_path)
    if data is None:
        return {}

    # Build a flat lookup: raw_value (lowercased) → {label}
    lookup: dict[str, dict] = {}
    for _category, values in data.items():
        if not isinstance(values, dict):
            continue
        for label, info in values.items():
            if not isinstance(info, dict):
                continue
            for alias in info.get("aliases", []):
                lookup[alias.lower()] = {"label": label}
    return lookup


def _extract_values(
    source_name: str,
    pairs: list[tuple[SemanticIdentity, ProvenanceEntry]],
    library_path: Path,
    registry: HashRegistry,
) -> dict[str, int]:
    """Extract enum values from element constraints and create ValueConcept files."""
    values_dir = library_path / "values"
    values_dir.mkdir(parents=True, exist_ok=True)

    value_mappings = _load_value_mappings(library_path)

    # Collect all raw enum values with their source
    raw_values: list[tuple[str, str]] = []  # (raw_value, source_name)
    for sem, prov in pairs:
        # Extract enum values from response_options
        if sem.response_options:
            for opt in sem.response_options:
                raw_values.append((opt.value, source_name))

    # Group by mapped identity
    value_groups: dict[str, tuple[ValueSemanticIdentity, list[ProvenanceEntry]]] = {}
    for raw_val, src in raw_values:
        mapping = value_mappings.get(raw_val.lower())
        if mapping:
            label = mapping["label"]
        else:
            label = raw_val.lower().replace(" ", "_")

        sem_id = ValueSemanticIdentity(
            value_type="categorical",
            label=label,
        )
        sem_dict = sem_id.model_dump(exclude_none=True)
        sha = compute_sha256(canonical_json(sem_dict))

        prov = ProvenanceEntry(source=src, **{"class": ""}, name=raw_val)

        if sha not in value_groups:
            value_groups[sha] = (sem_id, [])
        # Avoid duplicate provenance
        existing_raw = {(p.source, p.name) for p in value_groups[sha][1]}
        if (src, raw_val) not in existing_raw:
            value_groups[sha][1].append(prov)

    import uuid as _uuid

    created = 0
    for _sha, (sem_id, provs) in value_groups.items():
        # UUID filename (no hashing at extraction time — hash at commit)
        filepath = values_dir / f"{_uuid.uuid4()}.yaml"
        record = ValueConcept(semantic=sem_id, provenance=provs)
        data = record.model_dump(mode="json", exclude_none=True)
        filepath.write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        created += 1

        uri = build_value_uri(sem_id.label, filepath.stem)
        registry.elements[f"v_{filepath.stem}"] = HashRegistryEntry(
            sha256="",  # Hash computed at commit time
            attribute=sem_id.label,
            uri=uri,
        )

    return {"created": created}


def _ingest_extracted_values(
    value_pairs: list[tuple[ValueSemanticIdentity, ProvenanceEntry]],
    library_path: Path,
    registry: HashRegistry,
) -> int:
    """Write ValueConcept files from extracted value pairs (UUID filenames)."""
    import uuid as _uuid

    values_dir = library_path / "values"
    values_dir.mkdir(parents=True, exist_ok=True)

    # Dedup by (source, name) to avoid duplicate value files
    seen: set[tuple[str, str]] = set()
    created = 0
    for sem_id, prov in value_pairs:
        key = (prov.source, prov.name)
        if key in seen:
            continue
        seen.add(key)

        filepath = values_dir / f"{_uuid.uuid4()}.yaml"
        record = ValueConcept(semantic=sem_id, provenance=[prov])
        data = record.model_dump(mode="json", exclude_none=True)
        filepath.write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        created += 1

    return created


def _resolve_response_option_uris(library_path: Path) -> int:
    """Replace raw response_option values with ValueConcept URIs where a match exists."""
    elements_dir = library_path / "elements"
    values_dir = library_path / "values"

    if not values_dir.exists():
        return 0

    # Build lookup: raw_value (lowercased) → value URI
    value_lookup: dict[str, str] = {}
    for f in values_dir.glob("*.yaml"):
        data = safe_load_yaml(f)
        if data is None or "semantic" not in data:
            continue
        label = data["semantic"].get("label", "")
        uri = f"{BASE_URI}/values/{f.stem}"
        value_lookup[label.lower()] = uri
        for p in data.get("provenance", []):
            value_lookup[p.get("name", "").lower()] = uri

    resolved = 0
    for f in elements_dir.glob("*.yaml"):
        data = safe_load_yaml(f)
        if data is None or "semantic" not in data:
            continue
        opts = data["semantic"].get("response_options")
        if not opts:
            continue
        changed = False
        for opt in opts:
            raw = opt.get("value", "")
            match_uri = value_lookup.get(raw.lower())
            if match_uri and not opt.get("ontology_term"):
                opt["ontology_term"] = match_uri
                changed = True
        if changed:
            f.write_text(
                yaml.dump(data, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
            resolved += 1
    return resolved


def _extract(
    source_name: str, schema_path: Path | None
) -> tuple[list[tuple[SemanticIdentity, ProvenanceEntry]], list]:
    """Dispatch to adapter-based extraction.

    Returns (attribute_pairs, all_classified_entities).
    attribute_pairs: legacy tuple format for element pipeline.
    all_classified_entities: full list for valueset/enum routing.
    """
    from .adapters.registry import get_default_registry

    registry = get_default_registry()
    adapter = registry.get(source_name)

    # Determine source path — auto-acquire if not provided
    if schema_path is not None:
        path = schema_path
    else:
        try:
            from .acquisition import IsolatedEnv, SourceCache, load_source_def

            source_def = load_source_def(source_name)
            cache = SourceCache()
            cache_path = cache.acquire(source_def)

            if source_def.acquisition == "pip_install":
                # Run standalone extraction script in isolated venv
                iso = IsolatedEnv()
                env_path = iso.create_venv(source_def)
                try:
                    output = iso.install_and_run_adapter(
                        env_path,
                        source_def.package or source_def.name,
                        source_def.adapter,
                        extra_deps=source_def.extra_deps,
                    )

                    from .adapters.base import ClassifiedEntity
                    from .models import EntityType, SourceRef

                    ref = SourceRef(repo=source_def.repo, committish=None, file="", checksum="")
                    resolved_file = cache_path / "_resolved_committish"
                    if resolved_file.exists():
                        ref = SourceRef(
                            repo=source_def.repo,
                            committish=resolved_file.read_text().strip(),
                            file="",
                            checksum="",
                        )

                    if isinstance(output, str):
                        # LinkML YAML output — parse via LinkML adapter
                        import tempfile

                        from .adapters.linkml import LinkMLAdapter

                        with tempfile.NamedTemporaryFile(
                            suffix=".yaml", mode="w", delete=False
                        ) as tmp:
                            tmp.write(output)
                            tmp_path = Path(tmp.name)
                        try:
                            linkml_adapter = LinkMLAdapter()
                            entities = linkml_adapter.extract(
                                tmp_path,
                                source_name=source_name,
                                repo=source_def.repo,
                            )
                        finally:
                            tmp_path.unlink(missing_ok=True)
                    else:
                        # JSON entity list output
                        pip_entities = []
                        for item in output:
                            pip_entities.append(
                                ClassifiedEntity(
                                    entity_type=EntityType(item["entity_type"]),
                                    semantic=item["semantic"],
                                    provenance=item["provenance"],
                                    confidence=float(item.get("confidence", 0.8)),
                                    source_ref=ref,
                                )
                            )
                        entities = pip_entities
                    path = None
                finally:
                    iso.cleanup(env_path)
            else:
                # git_clone or download_file
                repo_path = cache_path / "_repo" if (cache_path / "_repo").exists() else cache_path
                if source_def.schema_path:
                    schema_dir = source_def.schema_path.split("/")[0]
                    candidate = repo_path / schema_dir
                    path = candidate if candidate.exists() else repo_path
                else:
                    path = repo_path
        except ImportError:
            # Acquisition module not available — try direct import (legacy)
            if source_name in ("bids", "dandi"):
                path = Path(".")
            else:
                raise ValueError(f"{source_name} requires --path to schema files")
        except Exception as exc:
            raise ValueError(f"{source_name}: auto-acquire failed: {exc}") from exc

    # For pip_install sources, entities are already extracted via isolated venv
    if path is not None:
        entities = adapter.extract(path)

    from .models import EntityType

    results: list[tuple[SemanticIdentity, ProvenanceEntry]] = []
    for entity in entities:
        if entity.entity_type != EntityType.ATTRIBUTE:
            continue

        sem_dict = entity.semantic
        dt = sem_dict.get("data_type", "string")
        response_options = None
        pattern = None

        if sem_dict.get("constraints"):
            c = sem_dict["constraints"]
            pattern = c.get("pattern")
        if sem_dict.get("pattern"):
            pattern = sem_dict["pattern"]
        if sem_dict.get("response_options"):
            response_options = [
                ResponseOption(**opt) if isinstance(opt, dict) else opt
                for opt in sem_dict["response_options"]
            ]

        sem = SemanticIdentity(
            data_type=dt,
            unit=sem_dict.get("unit"),
            unit_uri=sem_dict.get("unit_uri"),
            pattern=pattern,
            response_options=response_options,
            min_value=sem_dict.get("min_value"),
            max_value=sem_dict.get("max_value"),
            question_text=sem_dict.get("question_text"),
            value_domain=sem_dict.get("value_domain"),
            type_ref=sem_dict.get("type_ref"),
            description=sem_dict.get("description"),
        )

        prov_dict = entity.provenance
        prov = ProvenanceEntry(
            source=prov_dict.get("source", source_name),
            **{"class": prov_dict.get("class", "")},
            name=prov_dict.get("name", ""),
            description=prov_dict.get("description"),
        )
        results.append((sem, prov))

    return results, entities


def _process_classified_entities(
    entities: list, library_path: Path, source_name: str
) -> dict[str, int]:
    """Route non-ATTRIBUTE classified entities to valuesets/ and values/ directories."""
    from .models import EntityType

    valuesets_dir = library_path / "valuesets"
    valuesets_dir.mkdir(parents=True, exist_ok=True)
    values_dir = library_path / "values"
    values_dir.mkdir(parents=True, exist_ok=True)

    stats = {"valuesets_created": 0, "values_created": 0}

    for entity in entities:
        if entity.entity_type == EntityType.VALUESET:
            sem = entity.semantic
            name = sem.get("name", "unknown")
            members = sem.get("members", [])

            sem_dict = {"name": name, "members": sorted(members)}
            canonical = canonical_json(sem_dict)
            sha = compute_sha256(canonical)
            key = generate_short_key(sha)

            safe_name = sanitize_filename(name)
            filename = f"{safe_name}_{key}.yaml"
            filepath = valuesets_dir / filename

            if not filepath.exists():
                data = {
                    "sha256": sha,
                    "semantic": sem_dict,
                    "provenance": [entity.provenance],
                }
                filepath.write_text(
                    yaml.dump(data, default_flow_style=False, sort_keys=False),
                    encoding="utf-8",
                )
                stats["valuesets_created"] += 1

        elif entity.entity_type == EntityType.ENUM_VALUE:
            sem = entity.semantic
            label = sem.get("label", "")
            if not label:
                continue

            sem_dict = {
                "label": label,
                "value_type": sem.get("value_type", "categorical"),
            }
            if sem.get("description"):
                sem_dict["description"] = sem["description"]

            canonical = canonical_json(sem_dict)
            sha = compute_sha256(canonical)
            key = generate_short_key(sha)

            safe_label = sanitize_filename(label)
            filename = f"{safe_label}_{key}.yaml"
            filepath = values_dir / filename

            if filepath.exists():
                # Merge provenance
                existing = safe_load_yaml(filepath)
                if existing is None:
                    continue
                existing_sources = {
                    (p.get("source"), p.get("name", "")) for p in existing.get("provenance", [])
                }
                new_prov = entity.provenance
                if (new_prov.get("source"), new_prov.get("name", "")) not in existing_sources:
                    existing["provenance"].append(new_prov)
                    filepath.write_text(
                        yaml.dump(existing, default_flow_style=False, sort_keys=False),
                        encoding="utf-8",
                    )
            else:
                data = {
                    "sha256": sha,
                    "semantic": sem_dict,
                    "provenance": [entity.provenance],
                }
                filepath.write_text(
                    yaml.dump(data, default_flow_style=False, sort_keys=False),
                    encoding="utf-8",
                )
                stats["values_created"] += 1

    return stats


def _write_element(path: Path, record: ElementRecord, sha256: str | None = None) -> None:
    """Write an element record to YAML, with full SHA-256 for verification."""
    data = record.model_dump(mode="json", exclude_none=True, by_alias=True)
    if sha256:
        data["sha256"] = sha256
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


def _load_registry(path: Path) -> HashRegistry:
    """Load hash registry from YAML, or return empty."""
    if path.exists():
        data = safe_load_yaml(path)
        if data is not None:
            return HashRegistry.model_validate(data)
    return HashRegistry()


def _write_registry(path: Path, registry: HashRegistry) -> None:
    """Write hash registry to YAML."""
    data = registry.model_dump()
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


def _build_schemas_from_provenance(
    source_name: str,
    library_path: Path,
    registry: HashRegistry,
) -> dict[str, int]:
    """Build schema shape files by grouping elements by class from provenance."""
    from collections import defaultdict

    from .models import (
        ProvenanceEntry,
        SchemaIdentity,
        SchemaRecord,
    )

    elements_dir = library_path / "elements"
    schemas_dir = library_path / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)

    # Group element file references by (source, class)
    # During staging, element filenames are UUIDs — use file stem as reference.
    # These will be resolved to content-addressed URIs at commit time.
    class_elements: dict[str, list[str]] = defaultdict(list)

    for f in sorted(elements_dir.glob("*.yaml")):
        data = safe_load_yaml(f)
        if data is None or "provenance" not in data:
            continue
        for p in data["provenance"]:
            if p.get("source") == source_name:
                # Use element name as property reference
                name = p.get("name", f.stem)
                class_elements[p["class"]].append(name)

    created = 0

    import uuid as _uuid
    from datetime import datetime as dt_mod
    from datetime import timezone

    for class_name, element_names in class_elements.items():
        sorted_names = sorted(set(element_names))
        schema_id = SchemaIdentity(properties=sorted_names)

        now_iso = dt_mod.now(timezone.utc).isoformat()
        prov = ProvenanceEntry(
            source=source_name,
            **{"class": class_name},
            name=class_name,
            generated_at=now_iso,
            attributed_to="urn:undata:ingestion-pipeline",
            activity="ingestion",
        )

        # UUID filename (no hashing at extraction time)
        filepath = schemas_dir / f"{_uuid.uuid4()}.yaml"
        record = SchemaRecord(semantic=schema_id, provenance=[prov])
        data = record.model_dump(mode="json", exclude_none=True)
        filepath.write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )
        created += 1

    return {"created": created}


# Known unit conversion expressions (bidirectional)
_UNIT_CONVERSIONS: dict[tuple[str, str], dict] = {
    ("year", "iso8601_duration"): {
        "expression": "f'P{int(value)}Y'",
        "expression_type": "python_fstring",
        "reverse_expression": "int(value[1:-1])",
        "reverse_expression_type": "python",
        "function_type": "unit_conversion",
    },
    ("gram", None): {
        "expression": "str(value)",
        "expression_type": "python",
        "reverse_expression": "float(value)",
        "reverse_expression_type": "python",
        "function_type": "structural",
    },
}


def _generate_transform_mappings(
    library_path: Path,
    registry: HashRegistry,
) -> dict[str, int]:
    """Generate mapping files between elements sharing a primary ontology annotation
    but with different data_type or unit.

    For example: age (float, year) ↔ age (string, iso8601_duration)
    """
    from collections import defaultdict

    from .models import MappingProvenance, MappingRecord

    elements_dir = library_path / "elements"
    mappings_dir = library_path / "mappings"
    mappings_dir.mkdir(parents=True, exist_ok=True)

    # Group elements by primary ontology annotation URI
    onto_groups: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for f in sorted(elements_dir.glob("*.yaml")):
        data = safe_load_yaml(f)
        if data is None or "semantic" not in data:
            continue
        # Extract primary ontology URI from annotations
        annotations = data["semantic"].get("ontology_annotations", [])
        onto = None
        for ann in annotations:
            if ann.get("primary"):
                onto = ann.get("term_uri")
                break
        if onto:
            # Find URI from registry
            fname = f.stem
            parts = fname.rsplit("_", 1)
            if len(parts) == 2:
                key = parts[1]
                entry = registry.elements.get(key)
                if entry:
                    onto_groups[onto].append((entry.uri, data["semantic"]))

    created = 0
    existing_mapping_files = {f.stem for f in mappings_dir.glob("*.yaml")}

    for onto, elements in onto_groups.items():
        if len(elements) < 2:
            continue

        # Generate pairwise mappings between elements with different type/unit
        for i, (uri_a, sem_a) in enumerate(elements):
            for uri_b, sem_b in elements[i + 1 :]:
                if sem_a == sem_b:
                    continue  # Same hash — no mapping needed

                unit_a = sem_a.get("unit")
                unit_b = sem_b.get("unit")
                dt_a = sem_a.get("data_type")
                dt_b = sem_b.get("data_type")

                # Determine mapping type and expression
                conversion = _UNIT_CONVERSIONS.get((unit_a, unit_b))
                reverse_conversion = _UNIT_CONVERSIONS.get((unit_b, unit_a))

                if not conversion and not reverse_conversion:
                    # Try structural mapping (type change, no unit)
                    if dt_a != dt_b:
                        func_type = "structural"
                    else:
                        continue  # No meaningful mapping
                else:
                    func_type = "unit_conversion"

                # Forward mapping: A → B
                mapping_id = f"{uri_a}__to__{uri_b}".replace(f"{BASE_URI}/elements/", "")
                safe_id = mapping_id.replace("/", "_")[:80]

                if safe_id not in existing_mapping_files:
                    fwd = MappingRecord(
                        source_element=uri_a,
                        target_element=uri_b,
                        function_type=func_type,
                        expression=conversion["expression"] if conversion else None,
                        expression_type=(conversion["expression_type"] if conversion else None),
                        sssom_predicate="skos:closeMatch",
                        provenance=[MappingProvenance(source="curated")],
                    )
                    fwd_data = fwd.model_dump(mode="json", exclude_none=True)
                    (mappings_dir / f"{safe_id}.yaml").write_text(
                        yaml.dump(fwd_data, default_flow_style=False, sort_keys=False),
                        encoding="utf-8",
                    )
                    existing_mapping_files.add(safe_id)
                    created += 1

                # Reverse mapping: B → A
                rev_id = f"{uri_b}__to__{uri_a}".replace(f"{BASE_URI}/elements/", "")
                safe_rev = rev_id.replace("/", "_")[:80]

                if safe_rev not in existing_mapping_files:
                    rev_expr = conversion.get("reverse_expression") if conversion else None
                    rev_type = conversion.get("reverse_expression_type") if conversion else None
                    rev = MappingRecord(
                        source_element=uri_b,
                        target_element=uri_a,
                        function_type=func_type,
                        expression=rev_expr,
                        expression_type=rev_type,
                        sssom_predicate="skos:closeMatch",
                        provenance=[MappingProvenance(source="curated")],
                    )
                    rev_data = rev.model_dump(mode="json", exclude_none=True)
                    (mappings_dir / f"{safe_rev}.yaml").write_text(
                        yaml.dump(rev_data, default_flow_style=False, sort_keys=False),
                        encoding="utf-8",
                    )
                    existing_mapping_files.add(safe_rev)
                    created += 1

    return {"created": created}
