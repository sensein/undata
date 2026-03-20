"""Ingestion pipeline: raw schemas → content-addressed v2 YAML files."""

from __future__ import annotations

from pathlib import Path

import yaml

from .hashing import (
    build_element_uri,
    build_schema_uri,
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
    SemanticIdentity,
    ValueConcept,
    ValueProvenance,
    ValueSemanticIdentity,
)


def ingest_source(
    source_name: str,
    schema_path: Path | None,
    library_path: Path,
) -> dict[str, int]:
    """Ingest elements from a single source into the library.

    Returns stats: {created, merged, total}.
    """
    # Load extractor
    pairs = _extract(source_name, schema_path)

    # Apply curated element mappings (ontology annotations)
    element_mappings = _load_element_mappings(library_path)
    pairs = _apply_element_mappings(pairs, element_mappings)

    # Load existing hash registry
    registry_path = library_path / "hash-registry.yaml"
    registry = _load_registry(registry_path)
    existing_keys = set(registry.elements.keys())

    elements_dir = library_path / "elements"
    elements_dir.mkdir(parents=True, exist_ok=True)

    created = 0
    merged = 0

    # Group by semantic hash.
    # When the semantic graph is underspecified (no ontology_term, no unit,
    # no constraints), include the attribute name in the hash to prevent
    # unrelated properties from collapsing. The attribute name IS semantic
    # when no richer annotation exists.
    hash_to_records: dict[str, tuple[SemanticIdentity, list[ProvenanceEntry], str]] = {}

    for sem, prov in pairs:
        sem_dict = sem.model_dump(exclude_none=True)
        if "data_type" in sem_dict:
            sem_dict["data_type"] = str(sem_dict["data_type"])

        has_rich_semantics = sem.ontology_term is not None or sem.unit is not None
        if not has_rich_semantics:
            # Include attribute name + class as disambiguators when
            # the semantic graph is underspecified
            sem_dict["_attribute"] = prov.name
            sem_dict["_class"] = prov.class_

        sha = compute_sha256(canonical_json(sem_dict))

        if sha not in hash_to_records:
            hash_to_records[sha] = (sem, [], prov.name)
        hash_to_records[sha][1].append(prov)

    # Build reverse lookup: sha256 → existing key (for cross-invocation merging)
    sha_to_key: dict[str, str] = {entry.sha256: key for key, entry in registry.elements.items()}

    for sha, (sem, provs, first_name) in hash_to_records.items():
        # Check if this hash already exists in registry (from a prior ingest)
        if sha in sha_to_key:
            key = sha_to_key[sha]
        else:
            key = generate_short_key(sha, existing_keys)
            existing_keys.add(key)

        attr_name = first_name.lower()
        filename = f"{attr_name}_{key}.yaml"
        filepath = elements_dir / filename

        if filepath.exists():
            # Merge provenance into existing file
            existing_data = yaml.safe_load(filepath.read_text(encoding="utf-8"))
            existing_record = ElementRecord.model_validate(existing_data)
            existing_sources = {(p.source, p.name) for p in existing_record.provenance}

            new_provs = [p for p in provs if (p.source, p.name) not in existing_sources]
            if new_provs:
                all_provs = existing_record.provenance + new_provs
                record = ElementRecord(semantic=existing_record.semantic, provenance=all_provs)
                _write_element(filepath, record)
                merged += len(new_provs)
        else:
            record = ElementRecord(semantic=sem, provenance=provs)
            _write_element(filepath, record)
            created += 1

        # Update registry
        uri = build_element_uri(attr_name, key)
        registry.elements[key] = HashRegistryEntry(
            sha256=sha,
            attribute=attr_name,
            uri=uri,
        )

    # Write registry
    _write_registry(registry_path, registry)

    # Extract enum values as ValueConcepts
    value_stats = _extract_values(source_name, pairs, library_path, registry)
    _write_registry(registry_path, registry)

    # Build schema shapes from class groupings
    schema_stats = _build_schemas_from_provenance(source_name, library_path, registry)

    # Generate cross-element mappings for same ontology_term, different type/unit
    mapping_stats = _generate_element_mappings(library_path, registry)
    _write_registry(registry_path, registry)

    return {
        "created": created,
        "merged": merged,
        "total": len(hash_to_records),
        "schemas_created": schema_stats.get("created", 0),
        "values_created": value_stats.get("created", 0),
        "mappings_created": mapping_stats.get("created", 0),
    }


def _load_element_mappings(library_path: Path) -> dict[str, dict]:
    """Load element-mappings.yaml: attribute_name → {ontology_term, data_type, unit}."""
    path = library_path / "element-mappings.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _apply_element_mappings(
    pairs: list[tuple[SemanticIdentity, ProvenanceEntry]],
    mappings: dict[str, dict],
) -> list[tuple[SemanticIdentity, ProvenanceEntry]]:
    """Enrich elements with ontology annotations from curated mappings.

    Supports source_overrides: per-source data_type and unit overrides
    that produce different hashes (different elements) for the same concept
    when sources represent it differently.
    """
    if not mappings:
        return pairs

    enriched = []
    for sem, prov in pairs:
        mapping = mappings.get(prov.name)
        if mapping and sem.ontology_term is None:
            ontology_term = mapping.get("ontology_term")
            data_type = mapping.get("data_type") or str(sem.data_type)
            unit = mapping.get("unit") or sem.unit

            # Check for source-specific overrides
            overrides = mapping.get("source_overrides", {}).get(prov.source, {})
            if overrides:
                data_type = overrides.get("data_type", data_type)
                unit = overrides.get("unit", unit)

            sem = SemanticIdentity(
                ontology_term=ontology_term,
                data_type=data_type,
                unit=unit,
                constraints=sem.constraints,
            )
        enriched.append((sem, prov))
    return enriched


def _load_value_mappings(library_path: Path) -> dict[str, dict]:
    """Load value-mappings.yaml: raw_value → {ontology_term, label}."""
    mappings_path = library_path / "value-mappings.yaml"
    if not mappings_path.exists():
        return {}
    data = yaml.safe_load(mappings_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        return {}

    # Build a flat lookup: raw_value (lowercased) → {ontology_term, label}
    lookup: dict[str, dict] = {}
    for _category, values in data.items():
        if not isinstance(values, dict):
            continue
        for label, info in values.items():
            if not isinstance(info, dict):
                continue
            ontology_term = info.get("ontology_term")
            for alias in info.get("aliases", []):
                lookup[alias.lower()] = {
                    "ontology_term": ontology_term,
                    "label": label,
                }
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
    existing_keys = set(registry.elements.keys()) | set(registry.schemas.keys())

    # Collect all raw enum values with their source
    raw_values: list[tuple[str, str]] = []  # (raw_value, source_name)
    for sem, prov in pairs:
        if sem.constraints and sem.constraints.allowed_values:
            for val in sem.constraints.allowed_values:
                raw_values.append((val, source_name))

    # Group by mapped identity
    value_groups: dict[str, tuple[ValueSemanticIdentity, list[ValueProvenance]]] = {}
    for raw_val, src in raw_values:
        mapping = value_mappings.get(raw_val.lower())
        if mapping:
            label = mapping["label"]
            ontology_term = mapping["ontology_term"]
        else:
            label = raw_val.lower().replace(" ", "_")
            ontology_term = None

        sem_id = ValueSemanticIdentity(
            ontology_term=ontology_term,
            value_type="categorical",
            label=label,
        )
        sem_dict = sem_id.model_dump(exclude_none=True)
        sha = compute_sha256(canonical_json(sem_dict))

        prov = ValueProvenance(source=src, raw_value=raw_val)

        if sha not in value_groups:
            value_groups[sha] = (sem_id, [])
        # Avoid duplicate provenance
        existing_raw = {(p.source, p.raw_value) for p in value_groups[sha][1]}
        if (src, raw_val) not in existing_raw:
            value_groups[sha][1].append(prov)

    created = 0
    for sha, (sem_id, provs) in value_groups.items():
        key = generate_short_key(sha, existing_keys)
        existing_keys.add(key)

        safe_label = (
            sem_id.label.lower().replace("/", "_").replace("\\", "_").replace(" ", "_")[:50]
        )
        filename = f"{safe_label}_{key}.yaml"
        filepath = values_dir / filename

        if filepath.exists():
            existing_data = yaml.safe_load(filepath.read_text(encoding="utf-8"))
            existing_record = ValueConcept.model_validate(existing_data)
            existing_raw = {(p.source, p.raw_value) for p in existing_record.provenance}
            new_provs = [p for p in provs if (p.source, p.raw_value) not in existing_raw]
            if new_provs:
                all_provs = existing_record.provenance + new_provs
                record = ValueConcept(semantic=sem_id, provenance=all_provs)
                data = record.model_dump(mode="json", exclude_none=True)
                filepath.write_text(
                    yaml.dump(data, default_flow_style=False, sort_keys=False),
                    encoding="utf-8",
                )
        else:
            record = ValueConcept(semantic=sem_id, provenance=provs)
            data = record.model_dump(mode="json", exclude_none=True)
            filepath.write_text(
                yaml.dump(data, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
            created += 1

        uri = build_value_uri(sem_id.label, key)
        registry.elements[f"v_{key}"] = HashRegistryEntry(
            sha256=sha,
            attribute=sem_id.label,
            uri=uri,
        )

    return {"created": created}


def _extract(
    source_name: str, schema_path: Path | None
) -> list[tuple[SemanticIdentity, ProvenanceEntry]]:
    """Dispatch to source-specific extractor."""
    if source_name == "bids":
        from .extractors.bids import extract_bids

        return extract_bids()
    elif source_name == "dandi":
        from .extractors.dandi import extract_dandi

        return extract_dandi()
    elif source_name == "nwb":
        if schema_path is None:
            raise ValueError("NWB requires --path to schema YAML files")
        from .extractors.nwb import extract_nwb

        return extract_nwb(schema_path)
    elif source_name == "aind":
        if schema_path is None:
            raise ValueError("AIND requires --path to JSON Schema files")
        from .extractors.aind import extract_aind

        return extract_aind(schema_path)
    elif source_name == "openminds":
        if schema_path is None:
            raise ValueError("openMINDS requires --path to schema files")
        from .extractors.openminds import extract_openminds

        return extract_openminds(schema_path)
    else:
        raise ValueError(f"Unknown source: {source_name}")


def _write_element(path: Path, record: ElementRecord) -> None:
    """Write an element record to YAML."""
    data = record.model_dump(mode="json", exclude_none=True, by_alias=True)
    path.write_text(yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


def _load_registry(path: Path) -> HashRegistry:
    """Load hash registry from YAML, or return empty."""
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
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
        HashRegistryEntry,
        SchemaIdentity,
        SchemaProvenance,
        SchemaRecord,
    )

    elements_dir = library_path / "elements"
    schemas_dir = library_path / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)

    # Group element URIs by (source, class)
    class_elements: dict[str, list[str]] = defaultdict(list)

    for f in sorted(elements_dir.glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        if not data or "provenance" not in data:
            continue
        for p in data["provenance"]:
            if p.get("source") == source_name:
                # Find URI from registry by filename
                fname = f.stem  # e.g., "age_3c1gtm"
                parts = fname.rsplit("_", 1)
                if len(parts) == 2:
                    key = parts[1]
                    entry = registry.elements.get(key)
                    if entry:
                        class_elements[p["class"]].append(entry.uri)

    created = 0
    existing_schema_keys = set(registry.schemas.keys())

    for class_name, element_uris in class_elements.items():
        sorted_uris = sorted(set(element_uris))
        schema_id = SchemaIdentity(properties=sorted_uris)
        schema_dict = schema_id.model_dump(mode="json", exclude_none=True)
        canonical = canonical_json(schema_dict)
        sha = compute_sha256(canonical)
        key = generate_short_key(sha, existing_schema_keys)
        existing_schema_keys.add(key)

        filename = f"{class_name.lower()}_{key}.yaml"
        filepath = schemas_dir / filename

        prov = SchemaProvenance(source=source_name, name=class_name)

        if filepath.exists():
            existing = yaml.safe_load(filepath.read_text(encoding="utf-8"))
            existing_record = SchemaRecord.model_validate(existing)
            existing_sources = {p.source for p in existing_record.provenance}
            if source_name not in existing_sources:
                all_provs = existing_record.provenance + [prov]
                record = SchemaRecord(semantic=schema_id, provenance=all_provs)
                data = record.model_dump(mode="json", exclude_none=True)
                filepath.write_text(
                    yaml.dump(data, default_flow_style=False, sort_keys=False),
                    encoding="utf-8",
                )
        else:
            record = SchemaRecord(semantic=schema_id, provenance=[prov])
            data = record.model_dump(mode="json", exclude_none=True)
            filepath.write_text(
                yaml.dump(data, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
            created += 1

        uri = build_schema_uri(class_name, key)
        registry.schemas[key] = HashRegistryEntry(sha256=sha, name=class_name, uri=uri)

    # Re-write registry with schemas
    _write_registry(library_path / "hash-registry.yaml", registry)

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


def _generate_element_mappings(
    library_path: Path,
    registry: HashRegistry,
) -> dict[str, int]:
    """Generate mapping files between elements sharing an ontology_term but
    with different data_type or unit.

    For example: age (float, year) ↔ age (string, iso8601_duration)
    """
    from collections import defaultdict

    from .models import MappingProvenance, MappingRecord

    elements_dir = library_path / "elements"
    mappings_dir = library_path / "mappings"
    mappings_dir.mkdir(parents=True, exist_ok=True)

    # Group elements by ontology_term
    onto_groups: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for f in sorted(elements_dir.glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        if not data or "semantic" not in data:
            continue
        onto = data["semantic"].get("ontology_term")
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
                mapping_id = f"{uri_a}__to__{uri_b}".replace(
                    "https://schema.undata.live/elements/", ""
                )
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
                rev_id = f"{uri_b}__to__{uri_a}".replace("https://schema.undata.live/elements/", "")
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
