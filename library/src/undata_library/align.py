"""Alignment pipeline: alias detection + grouping + provenance tracking."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from .alias_detection import detect_aliases
from .embeddings import EmbeddingStore

if TYPE_CHECKING:
    from .storage.protocol import StorageBackend


def align_elements(
    elements_dir: Path | None = None,
    library_path: Path | None = None,
    threshold: float = 0.5,
    output_path: Path | None = None,
    dry_run: bool = False,
    *,
    backend: StorageBackend | None = None,
) -> dict:
    """Run alias detection, form groups, update provenance, produce alignment report.

    Returns stats dict.
    """
    if elements_dir is None and backend is not None and hasattr(backend, "base_dir"):
        elements_dir = backend.base_dir / "elements"
    lib_path = library_path or elements_dir.parent

    # Load embedding store if available
    embedding_store = _load_embedding_store(lib_path)

    # Run alias detection with embeddings
    candidates = detect_aliases(elements_dir, threshold=threshold, embedding_store=embedding_store)

    # Form alias groups via union-find
    exact_groups, close_groups = _form_alias_groups(candidates)

    # Load previous report for diffing
    report_path = output_path or (lib_path / "alignment-report.yaml")
    prev_report = _load_previous_report(report_path)

    # Compute diff
    diff = _compute_diff(exact_groups, close_groups, prev_report)

    # Update provenance on newly grouped elements
    if not dry_run:
        _update_provenance(elements_dir, exact_groups, close_groups, prev_report)

    # Build and persist report
    report = _build_report(exact_groups, close_groups, candidates, diff)
    if not dry_run:
        report_path.write_text(
            yaml.dump(report, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    return {
        "total_pairs_evaluated": len(candidates),
        "exact_match_groups": len(exact_groups),
        "close_match_groups": len(close_groups),
        "new_groups": diff.get("new_groups", 0),
        "unchanged_groups": diff.get("unchanged_groups", 0),
        "dissolved_groups": diff.get("dissolved_groups", 0),
    }


def _load_embedding_store(lib_path: Path) -> EmbeddingStore | None:
    """Load precomputed element embeddings if available.

    Checks multiple locations:
    1. lib_path/embeddings.parquet (legacy)
    2. lib_path/elements/embeddings.parquet (per-type)
    3. Build from Parquet entity files (entities with pre-computed embeddings)
    """
    for candidate in [
        lib_path / "embeddings.parquet",
        lib_path / "elements" / "embeddings.parquet",
    ]:
        if candidate.exists():
            try:
                store = EmbeddingStore(uri_col="uri").load(candidate)
                if store.size > 0:
                    return store
            except Exception:
                pass

    # Build from Parquet entity files that have pre-computed embeddings
    try:
        import numpy as np

        from .storage.parquet_store import ParquetStore
        from .utils import BASE_URI

        pq = ParquetStore(lib_path)
        uris = []
        vectors = []
        for entity in pq.list("elements"):
            emb = entity.get("embedding")
            if emb and isinstance(emb, list):
                sha = entity.get("sha256", "")
                uris.append(f"{BASE_URI}/elements/{sha}")
                vectors.append(np.array(emb, dtype=np.float32))

        if vectors:
            store = EmbeddingStore(uri_col="uri")
            store._uris = uris
            store._vectors = np.stack(vectors)
            store._model = "all-MiniLM-L6-v2"
            store._uri_to_idx = {u: i for i, u in enumerate(uris)}
            return store
    except Exception:
        pass

    return None


def _form_alias_groups(
    candidates: list[dict],
) -> tuple[list[list[str]], list[list[str]]]:
    """Group elements using union-find on exact matches; collect close matches separately."""

    # Union-find
    parent: dict[str, str] = {}

    def find(x: str) -> str:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    close_pairs: list[tuple[str, str, float]] = []

    for c in candidates:
        a, b = c["element_a"], c["element_b"]
        if c["relation"] == "skos:exactMatch":
            union(a, b)
        elif c["relation"] == "skos:closeMatch":
            close_pairs.append((a, b, c["score"]))

    # Collect exact match groups
    groups: dict[str, list[str]] = {}
    all_elements = set()
    for c in candidates:
        all_elements.add(c["element_a"])
        all_elements.add(c["element_b"])

    for elem in all_elements:
        root = find(elem)
        groups.setdefault(root, []).append(elem)

    exact_groups = [sorted(members) for members in groups.values() if len(members) > 1]

    # Collect close match groups (pairs, not transitive closure)
    close_groups: list[list[str]] = []
    for a, b, _score in close_pairs:
        close_groups.append(sorted([a, b]))

    return exact_groups, close_groups


def _load_previous_report(report_path: Path) -> dict | None:
    """Load previous alignment report for diffing."""
    if not report_path.exists():
        return None
    try:
        return yaml.safe_load(report_path.read_text(encoding="utf-8"))
    except (yaml.YAMLError, OSError):
        return None


def _compute_diff(
    exact_groups: list[list[str]],
    close_groups: list[list[str]],
    prev_report: dict | None,
) -> dict:
    """Compute diff between current and previous alignment."""
    if prev_report is None:
        return {
            "new_groups": len(exact_groups) + len(close_groups),
            "unchanged_groups": 0,
            "dissolved_groups": 0,
        }

    prev_groups_raw = prev_report.get("groups", [])
    prev_sets = {frozenset(g.get("members", [])) for g in prev_groups_raw}
    curr_sets = {frozenset(g) for g in exact_groups + close_groups}

    new_groups = len(curr_sets - prev_sets)
    unchanged_groups = len(curr_sets & prev_sets)
    dissolved_groups = len(prev_sets - curr_sets)

    return {
        "new_groups": new_groups,
        "unchanged_groups": unchanged_groups,
        "dissolved_groups": dissolved_groups,
    }


def _update_provenance(
    elements_dir: Path,
    exact_groups: list[list[str]],
    close_groups: list[list[str]],
    prev_report: dict | None,
) -> None:
    """Append alignment provenance to newly grouped elements."""
    # Determine which elements are newly in groups
    prev_members: set[str] = set()
    if prev_report:
        for g in prev_report.get("groups", []):
            prev_members.update(g.get("members", []))

    all_current = set()
    for g in exact_groups + close_groups:
        all_current.update(g)

    newly_grouped = all_current - prev_members
    if not newly_grouped:
        return

    now_iso = datetime.now(timezone.utc).isoformat()

    for fname in newly_grouped:
        fpath = elements_dir / fname
        if not fpath.exists():
            continue
        try:
            data = yaml.safe_load(fpath.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
        except (yaml.YAMLError, OSError):
            continue

        prov = data.get("provenance", [])
        prov.append(
            {
                "source": "alignment",
                "class": "",
                "name": "",
                "generated_at": now_iso,
                "attributed_to": "urn:undata:alignment-pipeline",
                "activity": "enrichment",
            }
        )
        data["provenance"] = prov
        fpath.write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )


def _build_report(
    exact_groups: list[list[str]],
    close_groups: list[list[str]],
    candidates: list[dict],
    diff: dict,
) -> dict:
    """Build alignment report YAML structure."""
    groups = []
    for g in exact_groups:
        groups.append({"members": g, "relation": "skos:exactMatch", "type": "exact"})
    for g in close_groups:
        groups.append({"members": g, "relation": "skos:closeMatch", "type": "close"})

    # Collect ungrouped elements
    grouped = set()
    for g in exact_groups + close_groups:
        grouped.update(g)

    all_elements = set()
    for c in candidates:
        all_elements.add(c["element_a"])
        all_elements.add(c["element_b"])

    ungrouped = sorted(all_elements - grouped)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "attributed_to": "urn:undata:alignment-pipeline",
        "stats": {
            "total_pairs_evaluated": len(candidates),
            "exact_match_groups": len(exact_groups),
            "close_match_groups": len(close_groups),
            **diff,
        },
        "groups": groups,
        "ungrouped": ungrouped,
    }
