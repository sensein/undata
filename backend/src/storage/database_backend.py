"""DatabaseBackend — StorageBackend protocol over PostgreSQL via SQLAlchemy async.

This module provides an async implementation of the StorageBackend protocol.
Methods are async (unlike FileBackend which is sync) because they use
SQLAlchemy's async session. GraphQL resolvers call these directly.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import AsyncIterator

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.models import (
    ENTITY_MODEL_MAP,
    CurationFlag as CurationFlagModel,
    RunSummary as RunSummaryModel,
)

from undata_library.models import CurationFlag, FlagStatus, FlagType, RunSummary

VALID_ENTITY_TYPES = frozenset(ENTITY_MODEL_MAP.keys())


class DatabaseEntityStore:
    """EntityStore implementation backed by PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    def _model(self, entity_type: str):
        if entity_type not in VALID_ENTITY_TYPES:
            raise ValueError(f"Invalid entity type: {entity_type!r}")
        return ENTITY_MODEL_MAP[entity_type]

    async def read(self, entity_type: str, identifier: str) -> dict | None:
        model = self._model(entity_type)
        # Try by sha256 prefix, then by file_name
        stmt = select(model).where(model.sha256.startswith(identifier)).limit(1)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            stmt = select(model).where(model.file_name == identifier).limit(1)
            result = await self._session.execute(stmt)
            row = result.scalar_one_or_none()
        if row is None:
            # Try exact file_name with .yaml
            stmt = select(model).where(model.file_name == f"{identifier}.yaml").limit(1)
            result = await self._session.execute(stmt)
            row = result.scalar_one_or_none()
        return self._row_to_dict(row) if row else None

    async def write(self, entity_type: str, data: dict, identifier: str | None = None) -> str:
        model = self._model(entity_type)
        sem = data.get("semantic", {})
        prov = data.get("provenance", [])
        annotations = sem.get("ontology_annotations", data.get("ontology_annotations", []))

        sha256 = data.get("sha256", "")
        if not sha256 and identifier:
            sha256 = identifier

        file_name = identifier or str(uuid.uuid4())

        kwargs = {
            "sha256": sha256 or str(uuid.uuid4()),
            "file_name": file_name,
            "semantic": sem,
            "provenance": prov,
            "ontology_annotations": annotations,
        }

        # Entity-type-specific columns
        if entity_type == "elements":
            kwargs.update({
                "data_type": sem.get("data_type"),
                "unit": sem.get("unit"),
                "unit_uri": sem.get("unit_uri"),
                "pattern": sem.get("pattern"),
                "value_domain": sem.get("value_domain"),
                "description": sem.get("description"),
                "min_value": sem.get("min_value"),
                "max_value": sem.get("max_value"),
                "type_ref": sem.get("type_ref"),
            })
        elif entity_type == "schemas":
            kwargs.update({
                "properties": sem.get("properties", []),
                "subclass_of": sem.get("subclass_of"),
                "is_mixin": sem.get("is_mixin", False),
                "description": sem.get("description"),
            })
        elif entity_type == "values":
            kwargs.update({
                "label": sem.get("label", ""),
                "value_type": sem.get("value_type"),
                "ontology_id": sem.get("ontology_id"),
                "description": sem.get("description"),
            })
        elif entity_type == "valuesets":
            kwargs.update({
                "name": sem.get("name", ""),
                "members": sem.get("members", []),
                "description": sem.get("description"),
            })

        # Compute embedding and search tsvector if model supports it
        if hasattr(model, "embedding") and model.embedding is not None:
            from src.services.embedding_service import build_search_text, compute_embedding
            from sqlalchemy import func

            search_text = build_search_text(entity_type, data)
            if search_text:
                embedding = compute_embedding(search_text)
                if embedding:
                    kwargs["embedding"] = embedding
                kwargs["search_tsv"] = func.to_tsvector("english", search_text)

        # Upsert by sha256
        stmt = pg_insert(model).values(**kwargs)
        update_set = {
            "provenance": stmt.excluded.provenance,
            "ontology_annotations": stmt.excluded.ontology_annotations,
            "semantic": stmt.excluded.semantic,
        }
        if "embedding" in kwargs:
            update_set["embedding"] = stmt.excluded.embedding
        if "search_tsv" in kwargs:
            update_set["search_tsv"] = stmt.excluded.search_tsv
        stmt = stmt.on_conflict_do_update(
            index_elements=[model.sha256],
            set_=update_set,
        )
        await self._session.execute(stmt)
        await self._session.flush()
        return file_name

    async def list(self, entity_type: str, **filters) -> AsyncIterator[dict]:
        model = self._model(entity_type)
        stmt = select(model)

        source_filter = filters.get("source")
        has_annotations = filters.get("has_annotations")
        data_type_filter = filters.get("data_type")

        if source_filter is not None:
            # Filter by source in provenance JSONB array
            from sqlalchemy import literal_column
            from sqlalchemy.types import Boolean

            stmt = stmt.where(
                literal_column(f"provenance @> '[{{\"source\": \"{source_filter}\"}}]'::jsonb").cast(Boolean)  # noqa: E501
            )

        if has_annotations is not None:
            if has_annotations:
                stmt = stmt.where(func.jsonb_array_length(model.ontology_annotations) > 0)
            else:
                stmt = stmt.where(
                    (func.jsonb_array_length(model.ontology_annotations) == 0)
                    | (model.ontology_annotations.is_(None))
                )

        if data_type_filter is not None and entity_type == "elements":
            stmt = stmt.where(model.data_type == data_type_filter)

        stmt = stmt.order_by(model.created_at, model.id)
        result = await self._session.execute(stmt)
        for row in result.scalars():
            yield self._row_to_dict(row)

    async def exists(self, entity_type: str, identifier: str) -> bool:
        model = self._model(entity_type)
        stmt = select(func.count()).select_from(model).where(
            model.sha256.startswith(identifier) | (model.file_name == identifier)
        )
        result = await self._session.execute(stmt)
        return result.scalar() > 0

    async def delete(self, entity_type: str, identifier: str) -> bool:
        model = self._model(entity_type)
        stmt = delete(model).where(
            model.sha256.startswith(identifier) | (model.file_name == identifier)
        )
        result = await self._session.execute(stmt)
        await self._session.flush()
        return result.rowcount > 0

    async def merge_provenance(
        self, entity_type: str, identifier: str, provenance: list[dict]
    ) -> dict:
        data = await self.read(entity_type, identifier)
        if data is None:
            raise KeyError(f"Entity not found: {entity_type}/{identifier}")

        existing_prov = data.get("provenance", [])
        existing_keys = {(p.get("source", ""), p.get("name", "")) for p in existing_prov}
        for p in provenance:
            key = (p.get("source", ""), p.get("name", ""))
            if key not in existing_keys:
                existing_prov.append(p)
                existing_keys.add(key)

        model = self._model(entity_type)
        stmt = (
            update(model)
            .where(model.sha256.startswith(identifier) | (model.file_name == identifier))
            .values(provenance=existing_prov)
        )
        await self._session.execute(stmt)
        await self._session.flush()

        data["provenance"] = existing_prov
        return data

    async def count(self, entity_type: str, **filters) -> int:
        if not filters:
            model = self._model(entity_type)
            stmt = select(func.count()).select_from(model)
            result = await self._session.execute(stmt)
            return result.scalar()
        return sum(1 async for _ in self.list(entity_type, **filters))

    async def find_by_hash(self, entity_type: str, short_key: str) -> dict | None:
        model = self._model(entity_type)
        stmt = select(model).where(model.sha256.startswith(short_key)).limit(1)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._row_to_dict(row) if row else None

    @staticmethod
    def _row_to_dict(row) -> dict:
        """Convert an ORM row to a dict matching FileBackend's YAML structure."""
        d = {
            "semantic": row.semantic or {},
            "provenance": row.provenance or [],
            "_identifier": row.file_name or str(row.id),
        }
        if row.sha256:
            d["sha256"] = row.sha256
        annotations = row.ontology_annotations or []
        if annotations:
            d["semantic"]["ontology_annotations"] = annotations
        return d


class DatabaseFlagStore:
    """FlagStore implementation backed by PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def write_flag(self, flag: CurationFlag) -> str:
        flag_id = str(flag.id) if flag.id else str(uuid.uuid4())
        record = CurationFlagModel(
            id=uuid.UUID(flag_id) if len(flag_id) == 36 else uuid.uuid4(),
            entity_type=flag.entity_type,
            entity_ref=flag.entity_ref,
            flag_type=flag.flag_type.value if isinstance(flag.flag_type, FlagType) else str(flag.flag_type),
            context=flag.context if isinstance(flag.context, dict) else {},
            status=flag.status.value if isinstance(flag.status, FlagStatus) else str(flag.status),
        )
        if hasattr(flag, "llm_verification") and flag.llm_verification:
            record.llm_verification = flag.llm_verification
        self._session.add(record)
        await self._session.flush()
        return str(record.id)

    async def read_flags(
        self,
        status: FlagStatus | str | None = None,
        flag_type: FlagType | str | None = None,
    ) -> list[CurationFlag]:
        stmt = select(CurationFlagModel)
        status_str = status.value if isinstance(status, FlagStatus) else status
        ftype_str = flag_type.value if isinstance(flag_type, FlagType) else flag_type

        if status_str:
            stmt = stmt.where(CurationFlagModel.status == status_str)
        if ftype_str:
            stmt = stmt.where(CurationFlagModel.flag_type == ftype_str)

        result = await self._session.execute(stmt)
        return [self._row_to_flag(r) for r in result.scalars()]

    async def resolve_flag(
        self,
        flag_id: str,
        action: FlagStatus | str,
        resolved_by: str,
        note: str | None = None,
    ) -> CurationFlag | None:
        try:
            uid = uuid.UUID(flag_id)
        except ValueError:
            return None

        stmt = select(CurationFlagModel).where(CurationFlagModel.id == uid)
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            return None

        action_str = action.value if isinstance(action, FlagStatus) else action
        row.status = action_str
        row.resolved_by = resolved_by
        row.resolved_at = datetime.now(timezone.utc).replace(tzinfo=None)
        if note:
            row.resolution_note = note
        await self._session.flush()
        return self._row_to_flag(row)

    @staticmethod
    def _row_to_flag(row) -> CurationFlag:
        return CurationFlag(
            id=str(row.id),
            entity_type=row.entity_type,
            entity_ref=row.entity_ref,
            flag_type=FlagType(row.flag_type) if row.flag_type else FlagType.needs_review,
            context=row.context or {},
            status=FlagStatus(row.status) if row.status else FlagStatus.pending,
            created_at=str(row.created_at) if row.created_at else "",
            resolved_at=str(row.resolved_at) if row.resolved_at else None,
            resolved_by=row.resolved_by,
            resolution_note=row.resolution_note,
        )


class DatabaseRunStore:
    """RunStore implementation backed by PostgreSQL."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def save_summary(self, summary: RunSummary) -> str:
        record = RunSummaryModel(
            run_id=summary.run_id,
            source=summary.source,
            started_at=summary.started_at,
            completed_at=getattr(summary, "completed_at", None),
            entity_counts=summary.entity_counts,
            enrichment_rate=getattr(summary, "enrichment_rate", None),
            curation_flags=getattr(summary, "curation_flags", None),
            delta=getattr(summary, "delta", None),
            timing=getattr(summary, "timing", None),
        )
        self._session.add(record)
        await self._session.flush()
        return summary.run_id

    async def load_previous(self, source: str) -> RunSummary | None:
        stmt = (
            select(RunSummaryModel)
            .where(RunSummaryModel.source == source)
            .order_by(RunSummaryModel.started_at.desc())
            .limit(1)
        )
        result = await self._session.execute(stmt)
        row = result.scalar_one_or_none()
        return self._row_to_summary(row) if row else None

    async def list_runs(
        self, source: str | None = None, limit: int | None = None
    ) -> list[RunSummary]:
        stmt = select(RunSummaryModel).order_by(RunSummaryModel.started_at.desc())
        if source:
            stmt = stmt.where(RunSummaryModel.source == source)
        if limit:
            stmt = stmt.limit(limit)
        result = await self._session.execute(stmt)
        return [self._row_to_summary(r) for r in result.scalars()]

    @staticmethod
    def _row_to_summary(row) -> RunSummary:
        return RunSummary(
            run_id=row.run_id,
            source=row.source,
            started_at=row.started_at or "",
            completed_at=row.completed_at,
            entity_counts=row.entity_counts or {},
            enrichment_rate=row.enrichment_rate,
            curation_flags=row.curation_flags,
            delta=row.delta,
            timing=row.timing,
        )


class DatabaseBackend:
    """StorageBackend implementation over PostgreSQL.

    Methods are async (unlike FileBackend) because they use SQLAlchemy async.
    Satisfies the same semantic contract as the StorageBackend protocol.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._entities = DatabaseEntityStore(session)
        self._flags = DatabaseFlagStore(session)
        self._runs = DatabaseRunStore(session)

    @property
    def entities(self) -> DatabaseEntityStore:
        return self._entities

    @property
    def flags(self) -> DatabaseFlagStore:
        return self._flags

    @property
    def runs(self) -> DatabaseRunStore:
        return self._runs
