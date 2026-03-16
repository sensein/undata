"""Ingestion pipeline: raw schemas → content-addressed v2 YAML files."""

from __future__ import annotations

from pathlib import Path

import yaml

from .hashing import (
    build_element_uri,
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

    # Load existing hash registry
    registry_path = library_path / "hash-registry.yaml"
    registry = _load_registry(registry_path)
    existing_keys = set(registry.elements.keys())

    elements_dir = library_path / "elements"
    elements_dir.mkdir(parents=True, exist_ok=True)

    created = 0
    merged = 0

    # Group by semantic hash
    hash_to_records: dict[str, tuple[SemanticIdentity, list[ProvenanceEntry]]] = {}

    for sem, prov in pairs:
        sem_dict = sem.model_dump(exclude_none=True)
        # Normalize enum values to strings for hashing
        if "data_type" in sem_dict:
            sem_dict["data_type"] = str(sem_dict["data_type"])
        sha, _ = compute_sha256(canonical_json(sem_dict)), canonical_json(sem_dict)
        sha = compute_sha256(canonical_json(sem_dict))

        if sha not in hash_to_records:
            hash_to_records[sha] = (sem, [])
        hash_to_records[sha][1].append(prov)

    for sha, (sem, provs) in hash_to_records.items():
        key = generate_short_key(sha, existing_keys)
        existing_keys.add(key)

        # Determine attribute name (first provenance entry's name)
        attr_name = provs[0].name
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

    return {"created": created, "merged": merged, "total": len(hash_to_records)}


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
