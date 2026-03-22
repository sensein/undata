"""Commit stage: rehash enriched entities → content-addressed registry."""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from .hashing import compute_identity_hash, determine_hash_mode, generate_short_key
from .utils import safe_load_yaml, sanitize_filename


def commit_staged(staging_dir: Path, output_dir: Path) -> dict[str, int]:
    """Commit all staged entities to the registry.

    For each entity: determine hash mode → compute hash → write to output_dir.
    Merge provenance if target file already exists.
    Delete staging dir after successful commit.

    Returns stats: {committed, merged, per_type: {elements: N, ...}}
    """
    stats = {"committed": 0, "merged": 0, "per_type": {}}

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

    # Delete staging directory
    if staging_dir.exists():
        shutil.rmtree(staging_dir)

    return stats


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


def _merge_provenance(target: Path, new_data: dict) -> None:
    """Merge provenance from new_data into existing target file."""
    existing = safe_load_yaml(target)
    if existing is None:
        return

    existing_prov = existing.get("provenance", [])
    new_prov = new_data.get("provenance", [])

    # Dedup by (source, name)
    existing_keys = set()
    for p in existing_prov:
        if isinstance(p, dict):
            existing_keys.add((p.get("source", ""), p.get("name", "")))

    for p in new_prov:
        if isinstance(p, dict):
            key = (p.get("source", ""), p.get("name", ""))
            if key not in existing_keys:
                existing_prov.append(p)
                existing_keys.add(key)

    existing["provenance"] = existing_prov

    # Update ontology_annotations if new ones are richer
    new_anns = new_data.get("semantic", {}).get("ontology_annotations")
    if new_anns:
        existing.setdefault("semantic", {})["ontology_annotations"] = new_anns

    target.write_text(
        yaml.dump(existing, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
