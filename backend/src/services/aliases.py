"""AliasGroupService — alias group CRUD and similarity-based candidate detection."""

from __future__ import annotations

import uuid
from itertools import combinations
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.models.db import AliasGroup, AliasGroupMember, DataElement, DataElementVersion
from src.models.schemas import (
    AliasCandidatePair,
    AliasGroupCreate,
    AliasGroupUpdate,
    MappingFunctionCreate,
    SemanticGraphOverlap,
)
from src.services.audit import AuditService
from src.services.mappings import MappingService

logger = get_logger(__name__)


class AliasGroupNotFoundError(Exception):
    pass


def _compute_semantic_graph_overlap(
    sg_a: dict | None,
    sg_b: dict | None,
) -> SemanticGraphOverlap:
    """Compare two semantic_graph JSONB dicts and return overlap metrics."""
    if not sg_a:
        sg_a = {}
    if not sg_b:
        sg_b = {}

    # property_match: both have property.label and they match
    prop_a = (sg_a.get("property") or {}).get("label")
    prop_b = (sg_b.get("property") or {}).get("label")
    property_match = bool(prop_a and prop_b and prop_a == prop_b)

    # unit_match: both have unit.label and they match
    unit_a = (sg_a.get("unit") or {}).get("label")
    unit_b = (sg_b.get("unit") or {}).get("label")
    unit_match = bool(unit_a and unit_b and unit_a == unit_b)

    # entity_labels_match: sorted list of entity labels match
    entities_a = sorted(e.get("label", "") for e in (sg_a.get("entities") or []))
    entities_b = sorted(e.get("label", "") for e in (sg_b.get("entities") or []))
    entity_labels_match = entities_a == entities_b

    # domain_match: None when domain absent from both; bool otherwise
    domain_a = sg_a.get("domain")
    domain_b = sg_b.get("domain")
    if domain_a is None and domain_b is None:
        domain_match = None
    else:
        domain_match = domain_a == domain_b

    return SemanticGraphOverlap(
        property_match=property_match,
        unit_match=unit_match,
        entity_labels_match=entity_labels_match,
        domain_match=domain_match,
    )


class AliasGroupService:
    @staticmethod
    async def create(
        session: AsyncSession,
        data: AliasGroupCreate,
        actor_id: UUID,
    ) -> AliasGroup:
        """Create alias group and register identity MappingFunction for each unique pair."""
        from datetime import datetime, timezone

        group_id = uuid.uuid4()
        group = AliasGroup(
            id=group_id,
            name=data.name,
            sssom_predicate=data.sssom_predicate,
            confidence=data.confidence,
            detection_method=data.detection_method,
            created_at=datetime.now(timezone.utc),
        )
        session.add(group)
        await session.flush()

        # Add members
        for element_id in data.element_ids:
            member = AliasGroupMember(
                alias_group_id=group_id,
                element_id=element_id,
            )
            session.add(member)
        await session.flush()

        # Register identity mapping for each unique pair (A→B and B→A)
        for el_a, el_b in combinations(data.element_ids, 2):
            mapping_data = MappingFunctionCreate(
                function_type="identity",
                output_element_id=el_b,
                sssom_predicate=data.sssom_predicate,
                expression_type="identity",
                input_element_ids=[{"element_id": str(el_a), "position": 0}],
            )
            # CycleDetectedError propagates to caller → 409
            await MappingService.create(session, mapping_data, actor_id)

        await AuditService.record(
            session,
            record_type="AliasGroup",
            record_id=group_id,
            operation="create",
            actor_id=actor_id,
            version_num=None,
        )
        logger.info("alias_group.created", extra={"alias_group_id": str(group_id)})
        return group

    @staticmethod
    async def get(session: AsyncSession, alias_group_id: UUID) -> AliasGroup | None:
        result = await session.execute(select(AliasGroup).where(AliasGroup.id == alias_group_id))
        return result.scalar_one_or_none()

    @staticmethod
    async def list(
        session: AsyncSession,
        element_id: UUID | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[AliasGroup]]:
        query = select(AliasGroup)
        if element_id:
            query = query.join(
                AliasGroupMember, AliasGroup.id == AliasGroupMember.alias_group_id
            ).where(AliasGroupMember.element_id == element_id)

        count_result = await session.execute(select(func.count()).select_from(query.subquery()))
        total = count_result.scalar_one()

        result = await session.execute(query.limit(limit).offset(offset))
        return total, list(result.scalars().all())

    @staticmethod
    async def update(
        session: AsyncSession,
        alias_group_id: UUID,
        data: AliasGroupUpdate,
        actor_id: UUID,
    ) -> AliasGroup:
        group = await AliasGroupService.get(session, alias_group_id)
        if group is None:
            raise AliasGroupNotFoundError(f"AliasGroup {alias_group_id} not found")

        if data.name is not None:
            group.name = data.name
        if data.sssom_predicate is not None:
            group.sssom_predicate = data.sssom_predicate
        if data.confidence is not None:
            group.confidence = data.confidence

        # Add new members
        if data.add_element_ids:
            for element_id in data.add_element_ids:
                existing = await session.execute(
                    select(AliasGroupMember).where(
                        AliasGroupMember.alias_group_id == alias_group_id,
                        AliasGroupMember.element_id == element_id,
                    )
                )
                if existing.scalar_one_or_none() is None:
                    session.add(
                        AliasGroupMember(
                            alias_group_id=alias_group_id,
                            element_id=element_id,
                        )
                    )

        # Remove members
        if data.remove_element_ids:
            for element_id in data.remove_element_ids:
                member_result = await session.execute(
                    select(AliasGroupMember).where(
                        AliasGroupMember.alias_group_id == alias_group_id,
                        AliasGroupMember.element_id == element_id,
                    )
                )
                member = member_result.scalar_one_or_none()
                if member:
                    await session.delete(member)

        await session.flush()
        await AuditService.record(
            session,
            record_type="AliasGroup",
            record_id=alias_group_id,
            operation="update",
            actor_id=actor_id,
            version_num=None,
        )
        return group

    @staticmethod
    async def delete(
        session: AsyncSession,
        alias_group_id: UUID,
        actor_id: UUID,
    ) -> AliasGroup:
        group = await AliasGroupService.get(session, alias_group_id)
        if group is None:
            raise AliasGroupNotFoundError(f"AliasGroup {alias_group_id} not found")

        # Delete members first, then the group
        members_result = await session.execute(
            select(AliasGroupMember).where(AliasGroupMember.alias_group_id == alias_group_id)
        )
        for member in members_result.scalars().all():
            await session.delete(member)

        await session.delete(group)
        await session.flush()

        await AuditService.record(
            session,
            record_type="AliasGroup",
            record_id=alias_group_id,
            operation="delete",
            actor_id=actor_id,
            version_num=None,
        )
        return group

    @staticmethod
    async def detect(
        session: AsyncSession,
        source_id: UUID | None = None,
        threshold: float | None = None,
        cross_source_only: bool = False,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[AliasCandidatePair]]:
        """Find alias candidates using SimilarityService, with semantic graph overlap."""
        from src.core.config import settings
        from src.services.similarity import SimilarityService

        effective_threshold = (
            threshold if threshold is not None else settings.alias_similarity_threshold
        )

        # Resolve element_ids if source_id is specified
        element_ids: list[str] | None = None
        if source_id is not None:
            result = await session.execute(
                select(DataElement.id).where(
                    DataElement.source_id == source_id,
                    DataElement.deleted_at.is_(None),
                )
            )
            element_ids = [str(row) for row in result.scalars().all()]
            if not element_ids:
                return 0, []

        # Get candidates from similarity service (semantic_graph_overlap=None at this point)
        total, candidates = await SimilarityService.find_candidates(
            session,
            element_ids=element_ids,
            threshold=effective_threshold,
            limit=limit if not cross_source_only else limit * 10,  # over-fetch for filter
            offset=0 if cross_source_only else offset,
        )

        # Apply cross_source_only filter if requested
        if cross_source_only:
            filtered: list[AliasCandidatePair] = []
            for pair in candidates:
                if pair.element_a.source and pair.element_b.source:
                    if pair.element_a.source.id != pair.element_b.source.id:
                        filtered.append(pair)
                else:
                    # If source info missing, include conservatively
                    filtered.append(pair)
            total = len(filtered)
            candidates = filtered[offset : offset + limit]

        # Compute semantic_graph_overlap for each pair
        result_pairs: list[AliasCandidatePair] = []
        for pair in candidates:
            # Load semantic graphs for both elements
            ver_a_result = await session.execute(
                select(DataElementVersion.semantic_graph)
                .join(DataElement, DataElement.current_version_id == DataElementVersion.id)
                .where(DataElement.id == pair.element_a.id)
            )
            ver_b_result = await session.execute(
                select(DataElementVersion.semantic_graph)
                .join(DataElement, DataElement.current_version_id == DataElementVersion.id)
                .where(DataElement.id == pair.element_b.id)
            )
            sg_a = ver_a_result.scalar_one_or_none()
            sg_b = ver_b_result.scalar_one_or_none()

            overlap = _compute_semantic_graph_overlap(sg_a, sg_b)
            result_pairs.append(
                AliasCandidatePair(
                    element_a=pair.element_a,
                    element_b=pair.element_b,
                    similarity_score=pair.similarity_score,
                    suggested_predicate=pair.suggested_predicate,
                    semantic_graph_overlap=overlap,
                )
            )

        return total, result_pairs
