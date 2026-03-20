"""Post-ingestion ontology annotation — applies curated mappings as PROV-O curation events.

Replaces the pre-ingestion element-mappings.yaml approach. Ontology annotations
are now tracked as separate provenance entries with activity=curation.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from .hashing import canonical_json, compute_sha256, generate_short_key, build_element_uri
from .models import (
    HashRegistry,
    HashRegistryEntry,
)


def load_annotation_mappings(path: Path) -> dict[str, dict]:
    """Load annotation mappings (attribute_name → {ontology_term, ...})."""
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def annotate_elements(
    elements_dir: Path,
    mappings: dict[str, dict],
    annotator: str = "urn:undata:annotation-pipeline",
) -> dict[str, int]:
    """Apply ontology annotations to existing elements as curation events.

    For each element whose provenance name matches a mapping key:
    1. If the element already has the ontology_term → skip
    2. If the element has no ontology_term → create a NEW element file with
       the ontology_term set, and add a curation provenance entry.
       The original element gets a derived_from link.

    Returns: {annotated, skipped, already_annotated}
    """
    now_iso = datetime.now(timezone.utc).isoformat()
    stats = {"annotated": 0, "skipped": 0, "already_annotated": 0}

    # Load registry for key generation
    registry_path = elements_dir.parent / "hash-registry.yaml"
    registry = _load_registry(registry_path)
    existing_keys = set(registry.elements.keys())

    for f in sorted(elements_dir.glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        if not data or "semantic" not in data:
            continue

        # Already has ontology_term
        if data["semantic"].get("ontology_term"):
            stats["already_annotated"] += 1
            continue

        # Check if any provenance name matches a mapping
        matched_mapping = None
        for p in data.get("provenance", []):
            name = p.get("name", "")
            if name in mappings:
                matched_mapping = mappings[name]
                break

        if not matched_mapping:
            stats["skipped"] += 1
            continue

        # Apply annotation: update the semantic block
        old_uri = f"https://schema.undata.live/elements/{f.stem}"

        new_semantic = dict(data["semantic"])
        new_semantic["ontology_term"] = matched_mapping["ontology_term"]

        # Apply source-specific overrides if present
        # (for elements where the source provenance dictates different type/unit)
        for p in data.get("provenance", []):
            source = p.get("source", "")
            overrides = matched_mapping.get("source_overrides", {}).get(source, {})
            if overrides:
                if "data_type" in overrides:
                    new_semantic["data_type"] = overrides["data_type"]
                if "unit" in overrides:
                    new_semantic["unit"] = overrides["unit"]
                break  # Apply first matching source override

        if "unit" not in new_semantic and "unit" in matched_mapping:
            new_semantic["unit"] = matched_mapping["unit"]

        # Compute new hash
        sem_dict = dict(new_semantic)
        if "data_type" in sem_dict:
            sem_dict["data_type"] = str(sem_dict["data_type"])
        # Remove non-hash fields
        for k in ("question_text", "value_domain"):
            sem_dict.pop(k, None)

        sha = compute_sha256(canonical_json(sem_dict))
        key = generate_short_key(sha, existing_keys)
        existing_keys.add(key)

        attr_name = data["provenance"][0]["name"].lower()
        new_filename = f"{attr_name}_{key}.yaml"
        new_filepath = elements_dir / new_filename

        # Build new provenance list: original provenance + curation entry
        new_provenance = list(data.get("provenance", []))
        new_provenance.append(
            {
                "source": "curation",
                "class": "annotation",
                "name": attr_name,
                "description": f"Ontology annotation: {matched_mapping['ontology_term']}",
                "generated_at": now_iso,
                "attributed_to": annotator,
                "activity": "curation",
                "derived_from": old_uri,
            }
        )

        new_data = {"semantic": new_semantic, "provenance": new_provenance}

        # Write the annotated element (may be same file if hash didn't change,
        # or a new file if ontology_term changed the hash)
        new_filepath.write_text(
            yaml.dump(new_data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

        # Update registry
        new_uri = build_element_uri(attr_name, key)
        registry.elements[key] = HashRegistryEntry(
            sha256=sha,
            attribute=attr_name,
            uri=new_uri,
        )

        stats["annotated"] += 1

    # Save registry
    _write_registry(registry_path, registry)

    return stats


def build_ontology_index(elements_dir: Path) -> dict:
    """Build a reverse index: ontology_term → list of element URIs + metadata.

    This is a derived view — regenerated from element files on demand.
    """
    index: dict[str, list[dict]] = {}

    for f in sorted(elements_dir.glob("*.yaml")):
        data = yaml.safe_load(f.read_text(encoding="utf-8"))
        if not data or "semantic" not in data:
            continue

        onto = data["semantic"].get("ontology_term")
        if not onto:
            continue

        uri = f"https://schema.undata.live/elements/{f.stem}"
        sources = sorted({p.get("source", "") for p in data.get("provenance", [])})
        names = sorted({p.get("name", "") for p in data.get("provenance", [])})

        entry = {
            "uri": uri,
            "file": f.name,
            "data_type": data["semantic"].get("data_type"),
            "unit": data["semantic"].get("unit"),
            "sources": sources,
            "names": names,
        }

        index.setdefault(onto, []).append(entry)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ontology_term_count": len(index),
        "element_count": sum(len(v) for v in index.values()),
        "terms": index,
    }


def _load_registry(path: Path) -> HashRegistry:
    if path.exists():
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return HashRegistry.model_validate(data)
    return HashRegistry()


def _write_registry(path: Path, registry: HashRegistry) -> None:
    data = registry.model_dump()
    path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
