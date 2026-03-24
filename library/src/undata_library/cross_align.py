"""Cross-source alignment: detect matching entities and transfer annotations.

Scans the committed registry for entities that match across sources
(by label, by name, or by shared ontology URI) and transfers ontology
annotations from annotated to unannotated entities.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from .utils import safe_load_yaml

logger = logging.getLogger(__name__)


def cross_source_align(
    registry_dir: Path,
) -> dict[str, int]:
    """Align entities across sources by transferring ontology annotations.

    Scans all entity directories (elements, values, schemas, valuesets) for:
    1. Label matches: same label/name across different sources
    2. Ontology URI matches: same primary ontology annotation URI

    When a match is found and one entity has annotations but the other doesn't,
    the annotations are transferred.

    Returns: {label_matches, uri_matches, annotations_transferred, total_scanned}
    """
    stats = {
        "label_matches": 0,
        "uri_matches": 0,
        "annotations_transferred": 0,
        "total_scanned": 0,
    }

    # Build indices across all entity types
    by_label: dict[str, list[dict]] = {}  # label → [{path, source, anns, ...}]
    by_onto_uri: dict[str, list[dict]] = {}  # ontology_uri → [{path, source, ...}]

    for entity_type in ("elements", "values", "schemas", "valuesets"):
        entity_dir = registry_dir / entity_type
        if not entity_dir.exists():
            continue

        for f in sorted(entity_dir.glob("*.yaml")):
            data = safe_load_yaml(f)
            if data is None or "semantic" not in data:
                continue
            stats["total_scanned"] += 1

            sem = data["semantic"]
            prov = data.get("provenance", [{}])
            first_prov = prov[0] if prov and isinstance(prov[0], dict) else {}
            source = first_prov.get("source", "")
            name = first_prov.get("name", "")
            label = sem.get("label", name).lower()

            anns = sem.get("ontology_annotations", [])
            onto_id = sem.get("ontology_id")

            entry = {
                "path": str(f),
                "entity_type": entity_type,
                "source": source,
                "name": name,
                "label": label,
                "anns": anns,
                "onto_id": onto_id,
                "has_onto": bool(anns or onto_id),
            }

            if label:
                by_label.setdefault(label, []).append(entry)

            # Index by primary ontology URI
            if anns:
                primary = next((a for a in anns if a.get("primary")), anns[0])
                uri = primary.get("term_uri", "")
                if uri:
                    by_onto_uri.setdefault(uri, []).append(entry)
            elif onto_id:
                by_onto_uri.setdefault(onto_id, []).append(entry)

    # Transfer annotations by label match
    for label, entries in by_label.items():
        if len(entries) < 2:
            continue
        sources = {e["source"] for e in entries}
        if len(sources) < 2:
            continue  # Same source — not cross-source

        stats["label_matches"] += 1

        # Find entries with annotations
        with_anns = [e for e in entries if e["has_onto"]]
        without_anns = [e for e in entries if not e["has_onto"]]

        if with_anns and without_anns:
            # Transfer from the best annotated entry
            donor = with_anns[0]
            donor_anns = donor["anns"]
            if not donor_anns and donor["onto_id"]:
                # Build annotation from onto_id
                donor_anns = [
                    {
                        "term_uri": donor["onto_id"],
                        "term_label": donor["name"],
                        "ontology": _ontology_from_uri(donor["onto_id"]),
                        "mapping_relation": "skos:exactMatch",
                        "match_level": "element_match",
                        "score": 1.0,
                        "model": "cross_source_transfer",
                        "primary": True,
                    }
                ]

            for recipient in without_anns:
                _transfer_annotations(
                    Path(recipient["path"]),
                    donor_anns,
                    donor["source"],
                )
                stats["annotations_transferred"] += 1

    # Transfer by ontology URI match
    for uri, entries in by_onto_uri.items():
        if len(entries) < 2:
            continue
        sources = {e["source"] for e in entries}
        if len(sources) < 2:
            continue

        stats["uri_matches"] += 1

    logger.info(
        "Cross-source alignment: %d label matches, %d URI matches, %d annotations transferred",
        stats["label_matches"],
        stats["uri_matches"],
        stats["annotations_transferred"],
    )
    return stats


def _transfer_annotations(
    target_path: Path,
    annotations: list[dict],
    donor_source: str,
) -> None:
    """Transfer ontology annotations to a target entity file."""
    data = safe_load_yaml(target_path)
    if data is None or "semantic" not in data:
        return

    # Mark as transferred
    transferred_anns = []
    for ann in annotations:
        new_ann = dict(ann)
        new_ann["model"] = f"cross_source_transfer:{donor_source}"
        transferred_anns.append(new_ann)

    data["semantic"]["ontology_annotations"] = transferred_anns
    target_path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


def _ontology_from_uri(uri: str) -> str:
    """Extract ontology prefix from term URI."""
    if "/obo/" in uri:
        part = uri.rsplit("/obo/", 1)[-1]
        prefix = part.split("_")[0]
        return prefix.lower()
    if "schema.org" in uri:
        return "schema.org"
    if "interlex" in uri:
        return "interlex"
    return "unknown"
