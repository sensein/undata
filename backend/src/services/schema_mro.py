"""MROService — C3 MRO linearization for DynamicSchema inheritance and mixin resolution.

Implements:
- c3_merge(): pure Python C3 linearization
- detect_cycle_in_adjacency(): pure cycle detection on adjacency dict
- check_depth_limit(): enforces max 20 inheritance levels
- deduplicate_elements_by_source_local_id(): deduplicates by source_local_id (child wins)
- MROService: async service with LRU cache for DB-backed MRO resolution
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import DynamicSchema, DynamicSchemaElement, SchemaMixin

logger = logging.getLogger(__name__)

MAX_DEPTH = 20


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------


class CycleError(Exception):
    """Raised when a circular inheritance or mixin dependency is detected."""


class DepthError(Exception):
    """Raised when schema inheritance depth exceeds MAX_DEPTH."""


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------


def c3_merge(sequences: list[list[Any]]) -> list[Any]:
    """C3 linearization merge algorithm.

    Takes a list of linearized sequences (each already in MRO order) and merges
    them according to the C3 algorithm (same as Python's MRO).

    Raises CycleError if linearization is inconsistent (cycle detected).
    """
    result: list[Any] = []
    seqs = [list(s) for s in sequences if s]

    while seqs:
        # Find the first "good head" — a candidate not in the tail of any sequence
        for seq in seqs:
            candidate = seq[0]
            if all(candidate not in s[1:] for s in seqs):
                result.append(candidate)
                # Remove candidate from the front of all sequences
                for s in seqs:
                    if s and s[0] == candidate:
                        s.pop(0)
                # Remove empty sequences
                seqs = [s for s in seqs if s]
                break
        else:
            raise CycleError(
                f"Inconsistent hierarchy (C3 merge failed). "
                f"Remaining sequences: {seqs}"
            )

    return result


def detect_cycle_in_adjacency(
    graph: dict[str, str | None],
    proposed_id: str,
    proposed_parent: str,
) -> bool:
    """Return True if setting proposed_id's parent to proposed_parent creates a cycle.

    graph: dict mapping schema_id → parent_id (or None for root schemas).
    """
    if proposed_id == proposed_parent:
        return True

    # Walk from proposed_parent upward; if we reach proposed_id, cycle exists
    visited = set()
    current = proposed_parent
    while current is not None:
        if current == proposed_id:
            return True
        if current in visited:
            break  # Already detected cycle elsewhere — stop
        visited.add(current)
        current = graph.get(current)

    return False


def check_depth_limit(depth: int) -> None:
    """Raise DepthError if depth > MAX_DEPTH."""
    if depth > MAX_DEPTH:
        raise DepthError(
            f"Schema inheritance depth {depth} exceeds maximum allowed depth of {MAX_DEPTH}."
        )


def deduplicate_elements_by_source_local_id(
    elements: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Deduplicate elements by source_local_id, keeping the first occurrence (MRO order = child first).

    When two schemas define the same source_local_id, the element appearing
    earlier in the list (higher MRO precedence — child wins over parent) is kept.
    A WARNING is logged for each collision per FR-011 / T065.
    """
    seen: dict[str, dict[str, Any]] = {}
    result: list[dict[str, Any]] = []

    for elem in elements:
        slid = elem.get("source_local_id") or ""
        # Elements without a source_local_id cannot override each other — always include them
        if not slid:
            result.append(elem)
            continue
        if slid not in seen:
            seen[slid] = elem
            result.append(elem)
        else:
            # Collision: log warning with structured fields
            winner = seen[slid]
            logger.warning(
                "MRO element collision on source_local_id='%s': "
                "'%s' (schema '%s') overrides '%s' (schema '%s')",
                slid,
                winner.get("name"),
                winner.get("source_schema"),
                elem.get("name"),
                elem.get("source_schema"),
                extra={
                    "event": "mro_element_collision",
                    "source_local_id": slid,
                    "winning_source": winner.get("source_schema"),
                    "losing_source": elem.get("source_schema"),
                    "winning_source_id": str(winner.get("source_schema_id", "")),
                    "losing_source_id": str(elem.get("source_schema_id", "")),
                },
            )

    return result


# ---------------------------------------------------------------------------
# MROService — DB-backed resolver with LRU cache
# ---------------------------------------------------------------------------

# Cache key: (schema_id_str, version_num) → ordered list of schema_id strings
_mro_cache: dict[tuple[str, int], list[str]] = {}
_MRO_CACHE_MAX = 256


def _evict_cache_if_full() -> None:
    if len(_mro_cache) >= _MRO_CACHE_MAX:
        # Evict oldest entry (FIFO approximation — Python 3.7+ dicts preserve insertion order)
        oldest_key = next(iter(_mro_cache))
        del _mro_cache[oldest_key]


def invalidate_mro_cache(schema_id: uuid.UUID) -> None:
    """Remove all cached MRO entries for a schema (called after schema mutations)."""
    keys_to_remove = [k for k in _mro_cache if k[0] == str(schema_id)]
    for k in keys_to_remove:
        del _mro_cache[k]


async def _resolve_mro(
    schema_id: uuid.UUID,
    db: AsyncSession,
    visited: set[str] | None = None,
) -> list[uuid.UUID]:
    """Recursively resolve C3 MRO for a DynamicSchema.

    Returns ordered list of schema UUIDs (self first, then parents/mixins in C3 order).
    Raises CycleError on circular references.
    """
    if visited is None:
        visited = set()

    schema_id_str = str(schema_id)
    if schema_id_str in visited:
        raise CycleError(f"Circular schema reference detected at schema {schema_id}")
    visited.add(schema_id_str)

    result = await db.execute(
        select(DynamicSchema).where(DynamicSchema.id == schema_id)
    )
    schema = result.scalar_one_or_none()
    if schema is None:
        return [schema_id]

    # Get ordered mixins
    mixin_result = await db.execute(
        select(SchemaMixin)
        .where(SchemaMixin.schema_id == schema_id)
        .order_by(SchemaMixin.position)
    )
    mixins = list(mixin_result.scalars().all())

    own = [schema_id]

    parent_mro: list[uuid.UUID] = []
    if schema.parent_id is not None:
        parent_mro = await _resolve_mro(schema.parent_id, db, visited=set(visited))

    mixin_mros: list[list[uuid.UUID]] = []
    for mixin in mixins:
        m_mro = await _resolve_mro(mixin.mixin_id, db, visited=set(visited))
        mixin_mros.append(m_mro)

    # Build merge sequences per C3 spec
    sequences: list[list[Any]] = [own]
    if parent_mro:
        sequences.append(parent_mro)
    for m_mro in mixin_mros:
        sequences.append(m_mro)
    # The linearization tail: parent + mixins in order
    tail: list[uuid.UUID] = []
    if schema.parent_id:
        tail.append(schema.parent_id)
    tail.extend(m.mixin_id for m in mixins)
    if tail:
        sequences.append(tail)

    return c3_merge(sequences)


async def resolve_mro(
    schema_id: uuid.UUID,
    db: AsyncSession,
) -> list[uuid.UUID]:
    """Return C3 MRO for schema_id, using the in-memory LRU cache."""
    result = await db.execute(
        select(DynamicSchema.version_num).where(DynamicSchema.id == schema_id)
    )
    version_row = result.first()
    if version_row is None:
        return [schema_id]

    version_num = version_row[0]
    cache_key = (str(schema_id), version_num)

    if cache_key in _mro_cache:
        return [uuid.UUID(s) for s in _mro_cache[cache_key]]

    mro = await _resolve_mro(schema_id, db)

    _evict_cache_if_full()
    _mro_cache[cache_key] = [str(s) for s in mro]

    return mro


async def compute_depth(
    schema_id: uuid.UUID,
    db: AsyncSession,
) -> int:
    """Return the inheritance depth of schema_id (number of ancestors via parent_id)."""
    depth = 0
    current_id: uuid.UUID | None = schema_id

    while current_id is not None:
        result = await db.execute(
            select(DynamicSchema.parent_id).where(DynamicSchema.id == current_id)
        )
        row = result.first()
        if row is None or row[0] is None:
            break
        current_id = row[0]
        depth += 1
        if depth > MAX_DEPTH + 1:
            break  # safety guard

    return depth


async def get_resolved_elements(
    schema_id: uuid.UUID,
    db: AsyncSession,
) -> list[dict[str, Any]]:
    """Return the fully resolved element list for a schema in C3 MRO order.

    Elements are deduplicated by source_local_id (child wins per FR-011).
    Each element dict includes source_schema and source_schema_id annotations.
    """

    mro = await resolve_mro(schema_id, db)

    all_elements: list[dict[str, Any]] = []

    for s_id in mro:
        schema_result = await db.execute(
            select(DynamicSchema).where(DynamicSchema.id == s_id)
        )
        schema = schema_result.scalar_one_or_none()
        if schema is None:
            continue

        # Fetch elements via join
        from src.models.db import DataElement, DataElementVersion

        elem_result = await db.execute(
            select(DataElement, DataElementVersion, DynamicSchemaElement.position)
            .join(DynamicSchemaElement, DynamicSchemaElement.element_id == DataElement.id)
            .outerjoin(DataElementVersion, DataElementVersion.id == DataElement.current_version_id)
            .where(
                DynamicSchemaElement.schema_id == s_id,
                DataElement.deleted_at.is_(None),
            )
            .order_by(DynamicSchemaElement.position)
        )

        for de, dev, _ in elem_result.all():
            all_elements.append(
                {
                    "element_id": de.id,
                    "source_local_id": de.source_local_id,
                    "name": dev.name if dev else de.source_local_id,
                    "data_type": dev.data_type if dev else "string",
                    "element_kind": de.element_kind,
                    "required": dev.required if dev else False,
                    "source_schema": schema.name,
                    "source_schema_id": s_id,
                    "override": s_id != schema_id,
                }
            )

    return deduplicate_elements_by_source_local_id(all_elements)
