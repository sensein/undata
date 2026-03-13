"""MappingService — mapping function CRUD with cycle detection and URI minting."""

from __future__ import annotations

import hashlib
import uuid
from uuid import UUID

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.core.uri import mint_mapping_uri
from src.models.db import (
    AliasGroup,
    AliasGroupMember,
    DataElement,
    MappingFunction,
    MappingFunctionVersion,
    MappingInput,
)
from src.models.schemas import MappingFunctionCreate, MappingFunctionUpdate
from src.services.audit import AuditService
from src.services.cycle_detection import CycleDetector

logger = get_logger(__name__)


class ElementNotFoundError(Exception):
    pass


class CycleDetectedError(Exception):
    def __init__(self, cycle_path: list[str]):
        self.cycle_path = cycle_path
        super().__init__(f"Cycle detected: {cycle_path}")


class VersionConflictError(Exception):
    pass


async def _load_adjacency(session: AsyncSession) -> list[tuple[str, str]]:
    """Load all mapping edges as (input_element_id, output_element_id) pairs."""
    result = await session.execute(
        select(MappingInput.element_id, MappingFunction.output_element_id)
        .join(MappingFunction, MappingInput.mapping_id == MappingFunction.id)
        .where(MappingFunction.status != "deleted")
    )
    return [(str(row.element_id), str(row.output_element_id)) for row in result.all()]


async def _verify_no_cycle_recursive_cte(
    session: AsyncSession,
    input_ids: list[UUID],
    output_id: UUID,
) -> list[str] | None:
    """Secondary cycle check using WITH RECURSIVE CTE for ACID safety."""
    if not input_ids:
        return None

    # Check if output is reachable from any input via existing mapping graph
    result = await session.execute(
        text(
            """
            WITH RECURSIVE reachable(element_id) AS (
                SELECT mi.element_id::text
                FROM mapping_input mi
                JOIN mapping_function mf ON mi.mapping_id = mf.id
                WHERE mf.output_element_id = ANY(:output_ids)
                  AND mf.status != 'deleted'
                UNION
                SELECT mi.element_id::text
                FROM mapping_input mi
                JOIN mapping_function mf ON mi.mapping_id = mf.id
                JOIN reachable r ON mf.output_element_id::text = r.element_id
                WHERE mf.status != 'deleted'
            )
            SELECT element_id FROM reachable WHERE element_id = ANY(:input_ids)
            """
        ).bindparams(
            output_ids=[str(output_id)],
            input_ids=[str(i) for i in input_ids],
        )
    )
    rows = result.fetchall()
    if rows:
        return [str(output_id)] + [row[0] for row in rows]
    return None


class MappingService:
    @staticmethod
    async def create(
        session: AsyncSession,
        data: MappingFunctionCreate,
        actor_id: UUID,
    ) -> MappingFunction:
        """Create a new mapping function with cycle detection and URI minting."""
        # 1. Validate element IDs exist
        all_element_ids = [item["element_id"] for item in (data.input_element_ids or [])]
        all_element_ids.append(str(data.output_element_id))

        for eid in all_element_ids:
            el_result = await session.execute(
                select(DataElement.id).where(DataElement.id == UUID(str(eid)))
            )
            if el_result.scalar_one_or_none() is None:
                raise ElementNotFoundError(f"Element {eid} not found")

        input_ids = [UUID(str(item["element_id"])) for item in (data.input_element_ids or [])]
        output_id = data.output_element_id

        # 2. Load full adjacency list
        adjacency = await _load_adjacency(session)

        # 3. DFS cycle check
        cycle = CycleDetector.detect_cycle_dfs(
            adjacency,
            [str(i) for i in input_ids],
            str(output_id),
        )
        if cycle:
            raise CycleDetectedError(cycle)

        # 4. Advisory lock to prevent concurrent cycle creation
        lock_key = int(hashlib.sha256(str(output_id).encode()).hexdigest()[:16], 16) % (2**31)
        await session.execute(text(f"SELECT pg_advisory_xact_lock({lock_key})"))

        # 5. Re-verify with WITH RECURSIVE CTE
        cycle2 = await _verify_no_cycle_recursive_cte(session, input_ids, output_id)
        if cycle2:
            raise CycleDetectedError(cycle2)

        # 6. Mint URI and create records
        mapping_id = uuid.uuid4()
        uri = mint_mapping_uri(str(mapping_id))

        mapping = MappingFunction(
            id=mapping_id,
            uri=uri,
            function_type=data.function_type,
            output_element_id=output_id,
            version_num=1,
            status="active",
        )
        session.add(mapping)
        await session.flush()

        # Input rows
        for item in data.input_element_ids or []:
            link = MappingInput(
                mapping_id=mapping.id,
                element_id=UUID(str(item["element_id"])),
                position=item.get("position", 0),
            )
            session.add(link)

        # First version
        version = MappingFunctionVersion(
            mapping_id=mapping.id,
            version_num=1,
            description=data.description,
            expression=data.expression,
            expression_type=data.expression_type,
            parameter_schema=data.parameter_schema,
            sssom_predicate=data.sssom_predicate,
            created_by=actor_id,
        )
        session.add(version)
        await session.flush()

        mapping.current_version_id = version.id
        await session.flush()

        # 7. Audit
        await AuditService.record(
            session,
            record_type="MappingFunction",
            record_id=mapping.id,
            operation="create",
            actor_id=actor_id,
            version_num=1,
        )

        # 8. Auto-create alias group for identity mappings
        if data.function_type == "identity":
            all_element_ids_for_alias = list(input_ids) + [output_id]
            if len(all_element_ids_for_alias) >= 2:
                alias_group = AliasGroup(
                    sssom_predicate=data.sssom_predicate or "skos:exactMatch",
                    detection_method="identity_mapping",
                )
                session.add(alias_group)
                await session.flush()
                for eid in all_element_ids_for_alias:
                    member = AliasGroupMember(
                        alias_group_id=alias_group.id,
                        element_id=eid,
                    )
                    session.add(member)
                await session.flush()

        logger.info("mapping.created", extra={"mapping_id": str(mapping.id), "uri": uri})
        return mapping

    @staticmethod
    async def get(session: AsyncSession, mapping_id: UUID) -> MappingFunction | None:
        result = await session.execute(
            select(MappingFunction).where(MappingFunction.id == mapping_id)
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def list(
        session: AsyncSession,
        source_element_id: UUID | None = None,
        target_element_id: UUID | None = None,
        function_type: str | None = None,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[MappingFunction]]:
        query = select(MappingFunction).where(MappingFunction.deleted_at.is_(None))

        if source_element_id:
            query = query.join(MappingInput, MappingFunction.id == MappingInput.mapping_id).where(
                MappingInput.element_id == source_element_id
            )
        if target_element_id:
            query = query.where(MappingFunction.output_element_id == target_element_id)
        if function_type:
            query = query.where(MappingFunction.function_type == function_type)
        if status:
            query = query.where(MappingFunction.status == status)

        count_result = await session.execute(select(func.count()).select_from(query.subquery()))
        total = count_result.scalar_one()

        result = await session.execute(query.limit(limit).offset(offset))
        return total, list(result.scalars().all())

    @staticmethod
    async def update(
        session: AsyncSession,
        mapping_id: UUID,
        data: MappingFunctionUpdate,
        actor_id: UUID,
        version_num: int,
    ) -> MappingFunction:
        mapping = await MappingService.get(session, mapping_id)
        if mapping is None:
            raise ValueError(f"Mapping {mapping_id} not found")
        if mapping.version_num != version_num:
            raise VersionConflictError(
                f"Version conflict: current={mapping.version_num}, provided={version_num}"
            )

        # Load current version for diff
        cur_ver_result = await session.execute(
            select(MappingFunctionVersion).where(
                MappingFunctionVersion.id == mapping.current_version_id
            )
        )
        cur_ver = cur_ver_result.scalar_one()

        new_version_num = mapping.version_num + 1
        new_version = MappingFunctionVersion(
            mapping_id=mapping.id,
            version_num=new_version_num,
            description=data.description if data.description is not None else cur_ver.description,
            expression=data.expression if data.expression is not None else cur_ver.expression,
            expression_type=data.expression_type
            if data.expression_type is not None
            else cur_ver.expression_type,
            parameter_schema=data.parameter_schema
            if data.parameter_schema is not None
            else cur_ver.parameter_schema,
            sssom_predicate=data.sssom_predicate
            if data.sssom_predicate is not None
            else cur_ver.sssom_predicate,
            created_by=actor_id,
        )
        session.add(new_version)
        await session.flush()

        mapping.current_version_id = new_version.id
        mapping.version_num = new_version_num
        await session.flush()

        await AuditService.record(
            session,
            record_type="MappingFunction",
            record_id=mapping.id,
            operation="update",
            actor_id=actor_id,
            version_num=new_version_num,
        )
        return mapping

    @staticmethod
    async def delete(
        session: AsyncSession,
        mapping_id: UUID,
        actor_id: UUID,
        version_num: int | None = None,
    ) -> MappingFunction:
        from datetime import datetime, timezone

        mapping = await MappingService.get(session, mapping_id)
        if mapping is None:
            raise ValueError(f"Mapping {mapping_id} not found")

        mapping.deleted_at = datetime.now(timezone.utc)
        mapping.status = "deleted"
        await session.flush()

        await AuditService.record(
            session,
            record_type="MappingFunction",
            record_id=mapping_id,
            operation="delete",
            actor_id=actor_id,
        )
        return mapping

    @staticmethod
    async def get_history(session: AsyncSession, mapping_id: UUID) -> list[MappingFunctionVersion]:
        result = await session.execute(
            select(MappingFunctionVersion)
            .where(MappingFunctionVersion.mapping_id == mapping_id)
            .order_by(MappingFunctionVersion.version_num.asc())
        )
        return list(result.scalars().all())

    @staticmethod
    async def accept_mapping(
        session: AsyncSession,
        mapping_id: UUID,
        confidence_threshold: float | None = None,
    ) -> MappingFunction:
        """Accept a pending_curation mapping, optionally gated by confidence_threshold (FR-014).

        Raises:
            ValueError: mapping not found, already active, or confidence below threshold.
        """
        result = await session.execute(
            select(MappingFunction).where(MappingFunction.id == mapping_id)
        )
        mapping = result.scalar_one_or_none()
        if mapping is None:
            raise ValueError(f"Mapping {mapping_id} not found")

        if mapping.status != "pending_curation":
            raise ValueError(
                f"Mapping {mapping_id} cannot be accepted: status is '{mapping.status}', "
                "expected 'pending_curation'"
            )

        if confidence_threshold is not None:
            score = mapping.confidence_score
            if score is None or score < confidence_threshold:
                raise ValueError(
                    f"Mapping confidence_score {score!r} is below threshold {confidence_threshold}"
                )

        mapping.status = "active"
        await session.flush()
        logger.info(
            "Mapping accepted",
            extra={"mapping_id": str(mapping_id), "confidence_score": mapping.confidence_score},
        )
        return mapping

