"""Alignment pipeline: intra-source dedup + cross-source alignment + graph persistence.

Two-layer alignment:
1. SchemaView dedup during extraction (primary — handled in adapters/linkml.py)
2. Post-commit alignment (this module) — verifies intra-source dedup,
   runs cross-source alignment via multi-signal scoring, forms groups,
   designates canonicals, writes alignment graph fields.
"""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

import yaml

from .similarity import (
    compute_alignment_score,
    normalize_name,
)

if TYPE_CHECKING:
    from .embeddings import EmbeddingStore
    from .storage.protocol import StorageBackend

logger = logging.getLogger(__name__)

ENTITY_TYPES = ("elements", "schemas", "values", "valuesets")

# Default weights for alignment scoring signals
DEFAULT_WEIGHTS = {"name": 0.3, "embedding": 0.3, "ontology": 0.25, "alias": 0.15}


def align_entities(
    registry_path: Path | None = None,
    entity_types: list[str] | None = None,
    threshold: float = 0.7,
    weights: dict | None = None,
    dry_run: bool = False,
    incremental: bool = False,
    *,
    backend: StorageBackend | None = None,
) -> dict:
    """Run alignment pipeline: intra-source dedup + cross-source alignment.

    Args:
        registry_path: Path to the registry directory containing entity Parquet files.
        entity_types: Entity types to align (default: all).
        threshold: Minimum composite score for alignment (default 0.7).
        weights: Signal weights dict (name, embedding, ontology, alias).
        dry_run: If True, compute groups but don't write alignment fields.
        incremental: If True, skip entities that already have alignment fields.
        backend: Optional StorageBackend (used for DB-backed alignment).

    Returns AlignmentReport dict.
    """
    from .storage.parquet_store import ParquetStore

    types = entity_types or list(ENTITY_TYPES)
    w = weights or DEFAULT_WEIGHTS

    if registry_path is None and backend is not None and hasattr(backend, "base_dir"):
        registry_path = backend.base_dir

    if registry_path is None:
        return _empty_report()

    pq = ParquetStore(registry_path)

    # Load embedding store for semantic similarity
    embedding_store = _load_embedding_store(registry_path)

    # Load search candidates (feedback loop)
    search_candidates = pq.read_candidates(resolved=False)

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_entities_processed": 0,
        "alignment_groups": 0,
        "canonical_entities": 0,
        "member_entities": 0,
        "unaligned_entities": 0,
        "conflicts": 0,
        "candidates_from_search": len(search_candidates),
        "entity_type_breakdown": {},
    }

    for entity_type in types:
        type_report = _align_entity_type(
            pq,
            entity_type,
            threshold=threshold,
            weights=w,
            dry_run=dry_run,
            incremental=incremental,
            embedding_store=embedding_store,
            search_candidates=search_candidates,
        )
        report["entity_type_breakdown"][entity_type] = type_report
        report["total_entities_processed"] += type_report["total"]
        report["alignment_groups"] += type_report["groups"]
        report["canonical_entities"] += type_report["canonicals"]
        report["member_entities"] += type_report["members"]
        report["unaligned_entities"] += type_report["unaligned"]
        report["conflicts"] += type_report["conflicts"]

    # Write alignment report
    if not dry_run:
        report_path = registry_path / "alignment-report.yaml"
        report_path.write_text(
            yaml.dump(report, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    return report


def _align_entity_type(
    pq: Any,
    entity_type: str,
    *,
    threshold: float,
    weights: dict,
    dry_run: bool,
    incremental: bool,
    embedding_store: "EmbeddingStore | None",
    search_candidates: list[dict],
) -> dict:
    """Align entities of a single type. Returns per-type stats."""
    # Load all entities
    entities = list(pq.list(entity_type))
    if not entities:
        return {
            "total": 0,
            "groups": 0,
            "canonicals": 0,
            "members": 0,
            "unaligned": 0,
            "conflicts": 0,
        }

    # Build index by sha256
    by_sha: dict[str, dict] = {}
    for e in entities:
        sha = e.get("sha256", "")
        if sha:
            by_sha[sha] = e

    # Filter for incremental mode
    if incremental:
        entities = [e for e in entities if not _has_alignment(e)]

    # Phase 1: Intra-source dedup verification
    intra_groups = _intra_source_dedup(entities)

    # Phase 2: Cross-source candidate generation
    cross_candidates = _generate_cross_source_candidates(
        entities, embedding_store, search_candidates, threshold
    )

    # Phase 3: Multi-signal scoring
    scored_pairs = _score_candidates(cross_candidates, entities, weights, embedding_store)

    # Phase 4: Group formation via union-find
    all_pairs = []
    for group in intra_groups:
        for i in range(1, len(group)):
            all_pairs.append((group[0], group[i], 1.0))
    for pair in scored_pairs:
        if pair["score"] >= threshold:
            all_pairs.append((pair["sha_a"], pair["sha_b"], pair["score"]))

    groups, conflicts = _form_groups(all_pairs, by_sha)

    # Phase 5: Canonical designation + field updates
    updates: dict[str, dict] = {}
    for group in groups:
        if len(group) < 2:
            continue
        canonical, members = _designate_canonical(group, by_sha)
        if canonical is None:
            continue
        # Set aligned_members on canonical
        updates[canonical] = {
            "aligned_members": members,
        }
        # Set aligned_to on each member
        for member_sha in members:
            score = next(
                (
                    p[2]
                    for p in all_pairs
                    if (p[0] == member_sha or p[1] == member_sha)
                    and (p[0] == canonical or p[1] == canonical)
                ),
                1.0,
            )
            updates[member_sha] = {
                "aligned_to": canonical,
                "alignment_score": score,
            }

    if not dry_run and updates:
        pq.update_alignment_fields(entity_type, updates)

    grouped_count = sum(len(g) for g in groups if len(g) >= 2)
    canonical_count = len([g for g in groups if len(g) >= 2])

    return {
        "total": len(entities),
        "groups": canonical_count,
        "canonicals": canonical_count,
        "members": grouped_count - canonical_count,
        "unaligned": len(entities) - grouped_count,
        "conflicts": conflicts,
    }


def _has_alignment(entity: dict) -> bool:
    """Check if entity already has alignment fields set."""
    sem = entity.get("semantic", {})
    if isinstance(sem, str):
        try:
            sem = json.loads(sem)
        except (json.JSONDecodeError, TypeError):
            return False
    return bool(sem.get("aligned_to") or sem.get("aligned_members"))


def _intra_source_dedup(entities: list[dict]) -> list[list[str]]:
    """Find intra-source duplicates: same source + same normalized name + same type + compatible range.

    Returns groups of sha256 hashes.
    """
    # Group by (source, normalized_name, data_type)
    buckets: dict[tuple, list[str]] = defaultdict(list)

    for e in entities:
        sha = e.get("sha256", "")
        if not sha:
            continue
        sem = e.get("semantic", {})
        if isinstance(sem, str):
            try:
                sem = json.loads(sem)
            except (json.JSONDecodeError, TypeError):
                continue
        prov = e.get("provenance", [])
        if isinstance(prov, str):
            try:
                prov = json.loads(prov)
            except (json.JSONDecodeError, TypeError):
                prov = []
        source = ""
        name = ""
        if isinstance(prov, list) and prov:
            source = prov[0].get("source", "")
            name = prov[0].get("name", "")
        elif isinstance(prov, dict):
            source = prov.get("source", "")
            name = prov.get("name", "")

        dt = sem.get("data_type", "")
        min_v = sem.get("min_value")
        max_v = sem.get("max_value")
        range_key = (min_v, max_v) if min_v is not None or max_v is not None else (None, None)

        norm_name = normalize_name(name) if name else ""
        if norm_name:
            key = (source, norm_name, dt, range_key)
            buckets[key].append(sha)

    return [shas for shas in buckets.values() if len(shas) > 1]


def _generate_cross_source_candidates(
    entities: list[dict],
    embedding_store: "EmbeddingStore | None",
    search_candidates: list[dict],
    threshold: float,
) -> list[tuple[str, str]]:
    """Generate candidate pairs for cross-source alignment.

    Strategy 1: Name blocking — normalized name match across different sources.
    Strategy 2: Embedding k-NN — top-k most similar across different sources.
    Strategy 3: Search feedback candidates.
    """
    candidates: set[tuple[str, str]] = set()

    # Build name → sha mapping
    name_buckets: dict[str, list[tuple[str, str]]] = defaultdict(
        list
    )  # norm_name → [(sha, source)]
    sha_to_entity: dict[str, dict] = {}

    for e in entities:
        sha = e.get("sha256", "")
        if not sha:
            continue
        sha_to_entity[sha] = e
        prov = e.get("provenance", [])
        if isinstance(prov, str):
            try:
                prov = json.loads(prov)
            except (json.JSONDecodeError, TypeError):
                prov = []
        source = ""
        name = ""
        if isinstance(prov, list) and prov:
            source = prov[0].get("source", "")
            name = prov[0].get("name", "")
        elif isinstance(prov, dict):
            source = prov.get("source", "")
            name = prov.get("name", "")

        norm = normalize_name(name) if name else ""
        if norm:
            name_buckets[norm].append((sha, source))

    # Strategy 1: Name blocking
    for norm_name, entries in name_buckets.items():
        if len(entries) < 2:
            continue
        # Only pair across different sources
        sources = {s for _, s in entries}
        if len(sources) < 2:
            continue
        shas = [sha for sha, _ in entries]
        for i in range(len(shas)):
            for j in range(i + 1, len(shas)):
                src_i = entries[i][1]
                src_j = entries[j][1]
                if src_i != src_j:
                    pair = tuple(sorted([shas[i], shas[j]]))
                    candidates.add(pair)

    # Strategy 2: Embedding k-NN (if embeddings available)
    if embedding_store is not None and embedding_store.size > 0:
        try:
            import numpy as np

            # Build embedding matrix
            shas_with_emb = []
            vectors = []
            for e in entities:
                sha = e.get("sha256", "")
                emb = e.get("embedding")
                if isinstance(emb, str):
                    try:
                        emb = json.loads(emb)
                    except (json.JSONDecodeError, TypeError):
                        emb = None
                if sha and emb and isinstance(emb, list):
                    shas_with_emb.append(sha)
                    vectors.append(np.array(emb, dtype=np.float32))

            if len(vectors) > 1:
                mat = np.stack(vectors)
                # Normalize for cosine similarity
                norms = np.linalg.norm(mat, axis=1, keepdims=True)
                norms[norms == 0] = 1.0
                mat_norm = mat / norms

                # Top-k per entity (k=10)
                k = min(10, len(vectors) - 1)
                sims = mat_norm @ mat_norm.T
                for i in range(len(shas_with_emb)):
                    top_k = np.argsort(sims[i])[-k - 1 : -1][::-1]
                    for j in top_k:
                        if j == i:
                            continue
                        if sims[i, j] < threshold * 0.8:  # Pre-filter
                            continue
                        pair = tuple(sorted([shas_with_emb[i], shas_with_emb[j]]))
                        candidates.add(pair)
        except Exception as exc:
            logger.warning("Embedding k-NN failed: %s", exc)

    # Strategy 3: Search feedback candidates
    for sc in search_candidates:
        a, b = sc.get("entity_a", ""), sc.get("entity_b", "")
        if a and b:
            candidates.add(tuple(sorted([a, b])))

    return list(candidates)


def _score_candidates(
    candidates: list[tuple[str, str]],
    entities: list[dict],
    weights: dict,
    embedding_store: "EmbeddingStore | None",
) -> list[dict]:
    """Score candidate pairs using multi-signal alignment scoring."""
    by_sha: dict[str, dict] = {}
    for e in entities:
        sha = e.get("sha256", "")
        if sha:
            by_sha[sha] = e

    scored = []
    for sha_a, sha_b in candidates:
        ea = by_sha.get(sha_a)
        eb = by_sha.get(sha_b)
        if ea is None or eb is None:
            continue

        score = compute_alignment_score(
            ea,
            eb,
            weights=weights,
            embedding_store=embedding_store,
            uri_a=sha_a,
            uri_b=sha_b,
        )
        scored.append(
            {
                "sha_a": sha_a,
                "sha_b": sha_b,
                "score": score["composite"],
                "signals": score,
            }
        )

    return scored


def _form_groups(
    pairs: list[tuple[str, str, float]],
    by_sha: dict[str, dict],
) -> tuple[list[list[str]], int]:
    """Form alignment groups via union-find with range compatibility check.

    Returns (groups, conflict_count).
    """
    parent: dict[str, str] = {}
    conflicts = 0

    def find(x: str) -> str:
        while parent.get(x, x) != x:
            parent[x] = parent.get(parent[x], parent[x])
            x = parent[x]
        return x

    def union(a: str, b: str) -> None:
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for sha_a, sha_b, score in pairs:
        # Range compatibility check
        if not _ranges_compatible(by_sha.get(sha_a, {}), by_sha.get(sha_b, {})):
            conflicts += 1
            continue
        union(sha_a, sha_b)

    # Collect groups
    groups_map: dict[str, list[str]] = defaultdict(list)
    all_shas = set()
    for sha_a, sha_b, _ in pairs:
        all_shas.add(sha_a)
        all_shas.add(sha_b)

    for sha in all_shas:
        root = find(sha)
        groups_map[root].append(sha)

    groups = [sorted(members) for members in groups_map.values() if len(members) >= 2]
    return groups, conflicts


def _ranges_compatible(entity_a: dict, entity_b: dict) -> bool:
    """Check if two entities have compatible ranges (identical or absent)."""
    sem_a = entity_a.get("semantic", {})
    sem_b = entity_b.get("semantic", {})
    if isinstance(sem_a, str):
        try:
            sem_a = json.loads(sem_a)
        except (json.JSONDecodeError, TypeError):
            sem_a = {}
    if isinstance(sem_b, str):
        try:
            sem_b = json.loads(sem_b)
        except (json.JSONDecodeError, TypeError):
            sem_b = {}

    min_a, max_a = sem_a.get("min_value"), sem_a.get("max_value")
    min_b, max_b = sem_b.get("min_value"), sem_b.get("max_value")

    # Both have no range → compatible
    if min_a is None and max_a is None and min_b is None and max_b is None:
        return True
    # One has range, other doesn't → compatible (absent = no constraint)
    if (min_a is None and max_a is None) or (min_b is None and max_b is None):
        return True
    # Both have range → must match
    return min_a == min_b and max_a == max_b


def _designate_canonical(
    group: list[str],
    by_sha: dict[str, dict],
) -> tuple[str | None, list[str]]:
    """Designate the canonical entity in an alignment group.

    For identical entities: earliest created_at wins.
    Returns (canonical_sha, list_of_member_shas).
    """
    if not group:
        return None, []

    # Sort by created_at (earliest first)
    def sort_key(sha: str) -> str:
        e = by_sha.get(sha, {})
        return e.get("created_at", "9999")

    sorted_group = sorted(group, key=sort_key)
    canonical = sorted_group[0]
    members = sorted_group[1:]
    return canonical, members


def _load_embedding_store(lib_path: Path) -> "EmbeddingStore | None":
    """Load precomputed element embeddings if available."""
    from .embeddings import EmbeddingStore

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

        pq_store = ParquetStore(lib_path)
        uris = []
        vectors = []
        for entity in pq_store.list("elements"):
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


def _empty_report() -> dict:
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_entities_processed": 0,
        "alignment_groups": 0,
        "canonical_entities": 0,
        "member_entities": 0,
        "unaligned_entities": 0,
        "conflicts": 0,
        "candidates_from_search": 0,
        "entity_type_breakdown": {},
    }
