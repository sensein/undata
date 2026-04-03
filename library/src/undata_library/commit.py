"""Commit stage: rehash enriched entities → content-addressed registry."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from .hashing import compute_identity_hash, determine_hash_mode
from .utils import safe_load_yaml

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .storage.protocol import StorageBackend


def commit_staged(
    staging_dir: Path | None = None,
    output_dir: Path | None = None,
    validate_sources: bool = False,
    known_sources: set[str] | None = None,
    *,
    staging_backend: StorageBackend | None = None,
    output_backend: StorageBackend | None = None,
) -> dict[str, int]:
    """Commit all staged entities to the registry.

    Accepts either Path arguments or StorageBackend arguments.

    For each entity: determine hash mode → compute hash → write to output_dir.
    Merge provenance if target file already exists.
    Delete staging dir after successful commit.

    If validate_sources=True, provenance sources are checked against known_sources.
    Entities with unrecognized sources are flagged as suspicious_source.

    Returns stats: {committed, merged, rejected, per_type: {elements: N, ...}}
    """
    if staging_dir is None and staging_backend is not None and hasattr(staging_backend, "base_dir"):
        staging_dir = staging_backend.base_dir
    if output_dir is None and output_backend is not None and hasattr(output_backend, "base_dir"):
        output_dir = output_backend.base_dir
    stats = {"committed": 0, "merged": 0, "rejected": 0, "per_type": {}}
    staging_to_sha256: dict[str, str] = {}

    from .staging import iter_staged
    from .storage.parquet_store import ParquetStore

    pq_registry = ParquetStore(output_dir)

    for entity_type in ("elements", "schemas", "values", "valuesets"):
        type_dir = staging_dir / entity_type
        if not type_dir.exists():
            continue

        out_dir = output_dir / entity_type
        out_dir.mkdir(parents=True, exist_ok=True)

        type_committed = 0
        type_merged = 0

        # Collect entities to commit — may write as Parquet batch
        committed_entities: list[dict] = []

        for data in iter_staged(staging_dir, entity_type):
            if not isinstance(data, dict) or "semantic" not in data:
                continue

            semantic = data["semantic"]
            provenance = data.get("provenance", [])

            # Source validation: reject unrecognized sources
            if validate_sources and known_sources:
                entity_sources = {p.get("source", "") for p in provenance if isinstance(p, dict)}
                unknown = entity_sources - known_sources - {""}
                if unknown:
                    from .curation import create_flag, write_flag
                    from .models import FlagType

                    flag = create_flag(
                        entity_type=entity_type.rstrip("s"),
                        entity_ref=data.get("_identifier", data.get("file_name", "")),
                        flag_type=FlagType.suspicious_source,
                        context={
                            "reason": f"unrecognized source(s): {', '.join(sorted(unknown))}",
                            "sources": sorted(unknown),
                        },
                    )
                    write_flag(output_dir, flag)
                    stats["rejected"] += 1
                    continue

            # Determine hash mode from ontology annotations
            annotations = semantic.get("ontology_annotations", [])
            ontology_anchored, primary_uri = determine_hash_mode(annotations)

            # Compute identity hash
            prov_dicts = [
                p if isinstance(p, dict) else p.model_dump(by_alias=True) for p in provenance
            ]
            sha256, _canonical = compute_identity_hash(
                semantic,
                prov_dicts,
                ontology_anchored=ontology_anchored,
                primary_ontology_uri=primary_uri,
            )
            # Record staging identifier → sha256 mapping for flag resolution
            staging_id = data.get("_identifier", data.get("file_name", ""))
            if staging_id:
                staging_to_sha256[staging_id] = sha256
                if "." in staging_id:
                    staging_to_sha256[staging_id.rsplit(".", 1)[0]] = sha256

            # Check if entity already exists in registry (for cross-source merge)
            existing = pq_registry.read(entity_type, sha256)
            if existing:
                # Merge provenance into existing
                existing_prov = existing.get("provenance", [])
                existing_keys = {
                    (p.get("source", ""), p.get("name", ""))
                    for p in existing_prov
                    if isinstance(p, dict)
                }
                for p in provenance:
                    pk = (p.get("source", ""), p.get("name", ""))
                    if isinstance(p, dict) and pk not in existing_keys:
                        existing_prov.append(p)
                data["provenance"] = existing_prov
                type_merged += 1
            else:
                type_committed += 1

            data["sha256"] = sha256
            data["file_name"] = _derive_name(data, entity_type)
            committed_entities.append(data)

        stats["per_type"][entity_type] = {"committed": type_committed, "merged": type_merged}
        stats["committed"] += type_committed
        stats["merged"] += type_merged

        # Compute embeddings for all committed entities in batch
        if committed_entities:
            try:
                from .embeddings import compute_entity_embeddings

                committed_entities = compute_entity_embeddings(committed_entities)
            except ImportError:
                logger.debug("sentence-transformers not available; skipping embeddings")

        # Write committed entities to Parquet (sole output format)
        if committed_entities:
            source = ""
            if committed_entities[0].get("provenance"):
                prov = committed_entities[0]["provenance"]
                if prov and isinstance(prov[0], dict):
                    source = prov[0].get("source", "committed")
            pq_registry.write_batch(entity_type, committed_entities, source=source or "committed")

    # Post-commit: resolve cross-references using ParquetStore
    _resolve_cross_references(output_dir, pq_registry)

    # Post-commit: resolve curation flag entity_refs from filenames to sha256 hashes
    _resolve_flag_entity_refs(output_dir, staging_to_sha256)

    # Delete staging directory
    if staging_dir.exists():
        shutil.rmtree(staging_dir)

    return stats


def _resolve_cross_references(output_dir: Path, pq_store=None) -> None:
    """Resolve schema properties, valueset members, and type_refs via ParquetStore.

    Reads all entities from ParquetStore, builds lookup dicts, resolves references,
    and writes back resolved entities.
    """
    from .storage.parquet_store import ParquetStore

    store = pq_store or ParquetStore(output_dir)

    # Build element (class, name) → sha256 lookup
    elem_by_class: dict[tuple[str, str], str] = {}
    elem_by_name: dict[str, str] = {}
    for data in store.list("elements"):
        sha = data.get("sha256", "")
        if not sha:
            continue
        for prov in data.get("provenance", []):
            if isinstance(prov, dict) and prov.get("name"):
                name = prov["name"]
                cls = prov.get("class", prov.get("class_", ""))
                if cls:
                    elem_by_class[(cls, name)] = sha
                    elem_by_class[(cls, name.lower())] = sha
                if name not in elem_by_name:
                    elem_by_name[name] = sha
                if name.lower() not in elem_by_name:
                    elem_by_name[name.lower()] = sha

    # Build value label → sha256 lookup
    val_lookup: dict[str, str] = {}
    for data in store.list("values"):
        sha = data.get("sha256", "")
        if not sha:
            continue
        label = data.get("label", data.get("semantic", {}).get("label", ""))
        if label:
            val_lookup.setdefault(label, sha)
            val_lookup.setdefault(label.lower(), sha)
        for prov in data.get("provenance", []):
            if isinstance(prov, dict) and prov.get("name"):
                name = prov["name"]
                val_lookup.setdefault(name, sha)
                val_lookup.setdefault(name.lower(), sha)

    # Update schema properties — class-aware resolution via ParquetStore
    if elem_by_class or elem_by_name:
        resolved_schemas = []
        for data in store.list("schemas"):
            sem = data.get("semantic", {})
            props = sem.get("properties", [])
            if not props:
                resolved_schemas.append(data)
                continue

            schema_class = ""
            for prov in data.get("provenance", []):
                if isinstance(prov, dict):
                    schema_class = prov.get("class", prov.get("class_", prov.get("name", "")))
                    break

            resolved = []
            changed = False
            for prop in props:
                if len(prop) == 64 and all(c in "0123456789abcdef" for c in prop):
                    resolved.append(prop)
                    continue
                sha = (
                    elem_by_class.get((schema_class, prop))
                    or elem_by_class.get((schema_class, prop.lower()))
                    or elem_by_name.get(prop)
                    or elem_by_name.get(prop.lower())
                )
                if sha:
                    resolved.append(sha)
                    changed = True
                else:
                    resolved.append(prop)
            if changed:
                sem["properties"] = resolved
                data["semantic"] = sem
            resolved_schemas.append(data)

        if resolved_schemas:
            source = _get_source(resolved_schemas)
            store.write_batch("schemas", resolved_schemas, source=source)

    # Update valueset members via ParquetStore
    if val_lookup:
        resolved_vs = []
        for data in store.list("valuesets"):
            sem = data.get("semantic", {})
            members = sem.get("members", [])
            if not members:
                resolved_vs.append(data)
                continue
            resolved = []
            changed = False
            for member in members:
                if len(member) == 64 and all(c in "0123456789abcdef" for c in member):
                    resolved.append(member)
                    continue
                sha = val_lookup.get(member) or val_lookup.get(member.lower())
                if sha:
                    resolved.append(sha)
                    changed = True
                else:
                    resolved.append(member)
            if changed:
                sem["members"] = resolved
                data["semantic"] = sem
            resolved_vs.append(data)

        if resolved_vs:
            source = _get_source(resolved_vs)
            store.write_batch("valuesets", resolved_vs, source=source)

    # Resolve element type_ref: class names → schema sha256 hashes
    schema_lookup: dict[str, str] = {}
    for data in store.list("schemas"):
        sha = data.get("sha256", "")
        if not sha:
            continue
        for prov in data.get("provenance", []):
            if isinstance(prov, dict):
                name = prov.get("name", prov.get("class", ""))
                if name:
                    schema_lookup[name] = sha
                    schema_lookup[name.lower()] = sha

    if schema_lookup:
        resolved_elems = []
        for data in store.list("elements"):
            sem = data.get("semantic", {})
            type_ref = sem.get("type_ref")
            if type_ref and len(type_ref) != 64:
                sha = schema_lookup.get(type_ref) or schema_lookup.get(type_ref.lower())
                if sha:
                    sem["type_ref"] = sha
                    data["semantic"] = sem
            resolved_elems.append(data)

        if resolved_elems:
            source = _get_source(resolved_elems)
            store.write_batch("elements", resolved_elems, source=source)


def _get_source(entities: list[dict]) -> str:
    """Extract source name from first entity's provenance."""
    if entities and entities[0].get("provenance"):
        prov = entities[0]["provenance"]
        if prov and isinstance(prov[0], dict):
            return prov[0].get("source", "committed")
    return "committed"


def _resolve_flag_entity_refs(
    output_dir: Path, staging_to_sha256: dict[str, str] | None = None
) -> None:
    """Resolve curation flag entity_refs from filenames to sha256 hashes.

    Uses the staging→sha256 mapping built during commit, plus committed
    entity files as fallback.
    """
    file_to_sha: dict[str, str] = dict(staging_to_sha256 or {})

    # Also build from committed entities as fallback
    for entity_type in ("elements", "schemas", "values", "valuesets"):
        entity_dir = output_dir / entity_type
        if not entity_dir.exists():
            continue
        for f in entity_dir.glob("*.yaml"):
            data = safe_load_yaml(f)
            if data and "sha256" in data:
                file_to_sha[f.stem] = data["sha256"]
                file_to_sha[f.name] = data["sha256"]

    if not file_to_sha:
        return

    # Update flag entity_refs
    flags_dir = output_dir / "curation-flags"
    if not flags_dir.exists():
        return

    updated = 0
    for f in flags_dir.glob("*.yaml"):
        data = safe_load_yaml(f)
        if not data:
            continue
        ref = data.get("entity_ref", "")
        # Check if ref is a filename (not already a sha256)
        if ref in file_to_sha:
            data["entity_ref"] = file_to_sha[ref]
            f.write_text(
                yaml.dump(data, default_flow_style=False, sort_keys=False),
                encoding="utf-8",
            )
            updated += 1

    if updated:
        logger.info("Resolved %d flag entity_refs to sha256 hashes", updated)


def _derive_name(data: dict, entity_type: str) -> str:
    """Derive a human-readable name for the entity filename."""
    semantic = data.get("semantic", {})
    provenance = data.get("provenance", [])

    if entity_type == "values":
        return semantic.get("label", "value")
    if entity_type == "valuesets":
        return semantic.get("name", "valueset")

    # Elements + schemas: use first provenance name
    if provenance:
        first = provenance[0]
        if isinstance(first, dict):
            return first.get("name", "unknown")
    return "unknown"


def _merge_provenance(
    target: Path,
    new_data: dict,
    output_dir: Path | None = None,
    max_novel_sources: int = 3,
) -> bool:
    """Merge provenance from new_data into existing target file.

    Returns True if new provenance was added, False if all was duplicate.
    If more than max_novel_sources distinct novel sources are merged,
    generates a provenance_bloat CurationFlag.
    """
    existing = safe_load_yaml(target)
    if existing is None:
        return False

    existing_prov = existing.get("provenance", [])
    new_prov = new_data.get("provenance", [])

    # Dedup by (source, name)
    existing_keys = set()
    existing_sources = set()
    for p in existing_prov:
        if isinstance(p, dict):
            existing_keys.add((p.get("source", ""), p.get("name", "")))
            existing_sources.add(p.get("source", ""))

    added = 0
    novel_sources: set[str] = set()
    for p in new_prov:
        if isinstance(p, dict):
            key = (p.get("source", ""), p.get("name", ""))
            if key not in existing_keys:
                existing_prov.append(p)
                existing_keys.add(key)
                added += 1
                src = p.get("source", "")
                if src and src not in existing_sources:
                    novel_sources.add(src)

    existing["provenance"] = existing_prov

    # Update ontology_annotations if new ones are richer
    new_anns = new_data.get("semantic", {}).get("ontology_annotations")
    if new_anns:
        existing.setdefault("semantic", {})["ontology_annotations"] = new_anns

    target.write_text(
        yaml.dump(existing, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )

    # Flag provenance bloat if many novel sources are merging
    if len(novel_sources) >= max_novel_sources and output_dir:
        from .curation import create_flag, write_flag
        from .models import FlagType

        flag = create_flag(
            entity_type="element",
            entity_ref=str(target.name),
            flag_type=FlagType.provenance_bloat,
            context={
                "reason": f"{len(novel_sources)} novel sources merged in one commit",
                "novel_sources": sorted(novel_sources),
                "total_provenance": len(existing_prov),
            },
        )
        write_flag(output_dir, flag)

    return added > 0
