"""Strawberry GraphQL schema for the undata registry.

Reads from the flat-file YAML registry directly (no database required).
This is the simplest path to a working GraphQL API — database-backed
resolvers can be added later for performance.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import strawberry
from strawberry.fastapi import GraphQLRouter

from .types import (
    CurationFlag,
    Element,
    ElementConnection,
    ElementEdge,
    FlagStatus,
    FlagType,
    OntologyAnnotation,
    PageInfo,
    ProvenanceEntry,
    RunSummary,
    Schema,
    Value,
    ValueSet,
)

# Registry directory — configurable via environment
_REGISTRY_DIR: Path | None = None


def set_registry_dir(path: Path) -> None:
    global _REGISTRY_DIR
    _REGISTRY_DIR = path


def _get_registry() -> Path:
    if _REGISTRY_DIR:
        return _REGISTRY_DIR
    import os
    return Path(os.environ.get("UNDATA_REGISTRY_DIR", str(Path.home() / ".local/share/undata/registry")))


def _load_yaml(path: Path) -> dict | None:
    import yaml
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _to_element(data: dict, file_name: str) -> Element:
    sem = data.get("semantic", {})
    prov_list = data.get("provenance", [])
    anns = sem.get("ontology_annotations", [])
    return Element(
        sha256=data.get("sha256"),
        data_type=sem.get("data_type"),
        unit=sem.get("unit"),
        pattern=sem.get("pattern"),
        value_domain=sem.get("value_domain"),
        description=sem.get("description"),
        min_value=sem.get("min_value"),
        max_value=sem.get("max_value"),
        type_ref=sem.get("type_ref"),
        ontology_annotations=[OntologyAnnotation(**a) for a in anns if isinstance(a, dict)],
        provenance=[
            ProvenanceEntry(
                source=p.get("source", ""),
                class_name=p.get("class", p.get("class_", "")),
                name=p.get("name", ""),
                description=p.get("description"),
                generated_at=p.get("generated_at"),
                attributed_to=p.get("attributed_to"),
                activity=p.get("activity"),
            )
            for p in prov_list if isinstance(p, dict)
        ],
        file_name=file_name,
    )


def _to_value(data: dict, file_name: str) -> Value:
    sem = data.get("semantic", {})
    prov_list = data.get("provenance", [])
    anns = sem.get("ontology_annotations", [])
    return Value(
        sha256=data.get("sha256"),
        label=sem.get("label", ""),
        value_type=sem.get("value_type"),
        description=sem.get("description"),
        ontology_id=sem.get("ontology_id"),
        ontology_annotations=[OntologyAnnotation(**a) for a in anns if isinstance(a, dict)],
        provenance=[
            ProvenanceEntry(
                source=p.get("source", ""),
                class_name=p.get("class", p.get("class_", "")),
                name=p.get("name", ""),
                description=p.get("description"),
            )
            for p in prov_list if isinstance(p, dict)
        ],
        file_name=file_name,
    )


@strawberry.type
class Query:
    @strawberry.field
    def element(self, sha256: str) -> Optional[Element]:
        """Look up a single element by sha256 hash."""
        registry = _get_registry()
        for f in (registry / "elements").glob(f"*_{sha256[:12]}.yaml"):
            data = _load_yaml(f)
            if data:
                return _to_element(data, f.name)
        return None

    @strawberry.field
    def browse_elements(
        self,
        source: Optional[str] = None,
        data_type: Optional[str] = None,
        first: int = 20,
        after: Optional[str] = None,
    ) -> ElementConnection:
        """Browse elements with optional filtering."""
        registry = _get_registry()
        elements_dir = registry / "elements"
        if not elements_dir.exists():
            return ElementConnection(edges=[], page_info=PageInfo(has_next_page=False, has_previous_page=False), total_count=0)

        all_files = sorted(elements_dir.glob("*.yaml"))

        # Apply filters
        filtered = []
        for f in all_files:
            data = _load_yaml(f)
            if data is None:
                continue
            sem = data.get("semantic", {})
            prov = data.get("provenance", [{}])
            first_prov = prov[0] if prov and isinstance(prov[0], dict) else {}

            if source and first_prov.get("source") != source:
                continue
            if data_type and sem.get("data_type") != data_type:
                continue
            filtered.append((f, data))

        total = len(filtered)

        # Cursor pagination
        start_idx = 0
        if after:
            for i, (f, _) in enumerate(filtered):
                if f.stem == after:
                    start_idx = i + 1
                    break

        page = filtered[start_idx : start_idx + first]
        edges = [
            ElementEdge(node=_to_element(data, f.name), cursor=f.stem)
            for f, data in page
        ]

        return ElementConnection(
            edges=edges,
            page_info=PageInfo(
                has_next_page=start_idx + first < total,
                has_previous_page=start_idx > 0,
                start_cursor=edges[0].cursor if edges else None,
                end_cursor=edges[-1].cursor if edges else None,
            ),
            total_count=total,
        )

    @strawberry.field
    def browse_values(
        self,
        source: Optional[str] = None,
        first: int = 20,
        after: Optional[str] = None,
    ) -> list[Value]:
        """Browse values with optional source filtering."""
        registry = _get_registry()
        values_dir = registry / "values"
        if not values_dir.exists():
            return []

        results = []
        for f in sorted(values_dir.glob("*.yaml")):
            if len(results) >= first:
                break
            data = _load_yaml(f)
            if data is None:
                continue
            if source:
                prov = data.get("provenance", [{}])
                if prov and isinstance(prov[0], dict) and prov[0].get("source") != source:
                    continue
            results.append(_to_value(data, f.name))

        return results

    @strawberry.field
    def run_summaries(self) -> list[RunSummary]:
        """List all pipeline run summaries."""
        registry = _get_registry()
        runs_dir = registry / "runs"
        if not runs_dir.exists():
            return []

        results = []
        for f in sorted(runs_dir.glob("*.yaml"), reverse=True):
            data = _load_yaml(f)
            if data is None:
                continue
            results.append(RunSummary(
                run_id=data.get("run_id", f.stem),
                source=data.get("source", ""),
                started_at=data.get("started_at", ""),
                completed_at=data.get("completed_at"),
                entity_counts=data.get("entity_counts", {}),
                enrichment_rate=data.get("enrichment_rate"),
                curation_flags=data.get("curation_flags"),
                delta=data.get("delta"),
                timing=data.get("timing"),
            ))
        return results


schema = strawberry.Schema(query=Query)
graphql_app = GraphQLRouter(schema)
