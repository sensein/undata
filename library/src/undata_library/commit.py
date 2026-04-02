"""Commit stage: rehash enriched entities → content-addressed registry."""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

logger = logging.getLogger(__name__)

import yaml

from .hashing import compute_identity_hash, determine_hash_mode, generate_short_key
from .utils import safe_load_yaml, sanitize_filename

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
    # Track staging filename → sha256 for flag entity_ref resolution
    staging_to_sha256: dict[str, str] = {}

    for entity_type in ("elements", "schemas", "values", "valuesets"):
        type_dir = staging_dir / entity_type
        if not type_dir.exists():
            continue

        out_dir = output_dir / entity_type
        out_dir.mkdir(parents=True, exist_ok=True)

        type_committed = 0
        type_merged = 0

        for staged_file in sorted(type_dir.glob("*.yaml")):
            try:
                data = yaml.safe_load(staged_file.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or "semantic" not in data:
                    continue
            except (yaml.YAMLError, OSError):
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
                        entity_ref=str(staged_file.name),
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
            key = generate_short_key(sha256)

            # Record staging filename → sha256 mapping for flag resolution
            staging_to_sha256[staged_file.name] = sha256
            staging_to_sha256[staged_file.stem] = sha256

            # Check if any existing file has this hash (for cross-source merge)
            existing_with_hash = list(out_dir.glob(f"*_{key}.yaml"))
            if existing_with_hash:
                target = existing_with_hash[0]
            else:
                name = _derive_name(data, entity_type)
                safe_name = sanitize_filename(name)
                target = out_dir / f"{safe_name}_{key}.yaml"

            if target.exists():
                # Merge provenance
                _merge_provenance(target, data)
                type_merged += 1
            else:
                # Write new file with sha256
                data["sha256"] = sha256
                target.write_text(
                    yaml.dump(data, default_flow_style=False, sort_keys=False),
                    encoding="utf-8",
                )
                type_committed += 1

        stats["per_type"][entity_type] = {"committed": type_committed, "merged": type_merged}
        stats["committed"] += type_committed
        stats["merged"] += type_merged

    # Post-commit: resolve schema properties and valueset members to sha256 hashes
    _resolve_cross_references(output_dir)

    # Post-commit: resolve curation flag entity_refs from filenames to sha256 hashes
    _resolve_flag_entity_refs(output_dir, staging_to_sha256)

    # Delete staging directory
    if staging_dir.exists():
        shutil.rmtree(staging_dir)

    return stats


def _resolve_cross_references(output_dir: Path) -> None:
    """Resolve schema properties and valueset members from names to sha256 hashes.

    After all entities are committed with their sha256 hashes, this step updates:
    - Schema properties: slot names → element sha256 hashes
    - Valueset members: value labels → value sha256 hashes

    Uses a name→sha256 lookup built from committed elements and values.
    """
    # Build element (class, name) → sha256 lookup for class-aware resolution
    # Key: (class_name, slot_name) → sha256
    elem_by_class: dict[tuple[str, str], str] = {}
    # Fallback: name → sha256 (first encountered)
    elem_by_name: dict[str, str] = {}
    elements_dir = output_dir / "elements"
    if elements_dir.exists():
        for f in elements_dir.glob("*.yaml"):
            data = safe_load_yaml(f)
            if not data or "sha256" not in data:
                continue
            sha = data["sha256"]
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
    values_dir = output_dir / "values"
    if values_dir.exists():
        for f in values_dir.glob("*.yaml"):
            data = safe_load_yaml(f)
            if not data or "sha256" not in data:
                continue
            sha = data["sha256"]
            sem = data.get("semantic", {})
            label = sem.get("label", "")
            if label:
                if label not in val_lookup:
                    val_lookup[label] = sha
                if label.lower() not in val_lookup:
                    val_lookup[label.lower()] = sha
            # Also index by provenance name
            for prov in data.get("provenance", []):
                if isinstance(prov, dict) and prov.get("name"):
                    name = prov["name"]
                    if name not in val_lookup:
                        val_lookup[name] = sha
                    if name.lower() not in val_lookup:
                        val_lookup[name.lower()] = sha

    # Update schema properties — class-aware resolution
    schemas_dir = output_dir / "schemas"
    if schemas_dir.exists() and (elem_by_class or elem_by_name):
        for f in schemas_dir.glob("*.yaml"):
            data = safe_load_yaml(f)
            if not data:
                continue
            sem = data.get("semantic", {})
            props = sem.get("properties", [])
            if not props:
                continue

            # Get the schema's class name from provenance
            schema_class = ""
            for prov in data.get("provenance", []):
                if isinstance(prov, dict):
                    schema_class = prov.get("class", prov.get("class_", prov.get("name", "")))
                    break

            resolved = []
            changed = False
            for prop in props:
                # If it's already a sha256 hash (64 hex chars), keep it
                if len(prop) == 64 and all(c in "0123456789abcdef" for c in prop):
                    resolved.append(prop)
                    continue
                # Class-aware: prefer element from same class as the schema
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
                    resolved.append(prop)  # Keep unresolved name
            if changed:
                sem["properties"] = resolved
                f.write_text(
                    yaml.dump(data, default_flow_style=False, sort_keys=False),
                    encoding="utf-8",
                )

    # Update valueset members
    valuesets_dir = output_dir / "valuesets"
    if valuesets_dir.exists() and val_lookup:
        for f in valuesets_dir.glob("*.yaml"):
            data = safe_load_yaml(f)
            if not data:
                continue
            sem = data.get("semantic", {})
            members = sem.get("members", [])
            if not members:
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
                f.write_text(
                    yaml.dump(data, default_flow_style=False, sort_keys=False),
                    encoding="utf-8",
                )


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
