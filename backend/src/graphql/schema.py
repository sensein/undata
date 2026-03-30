"""Strawberry GraphQL schema — Query + Mutation wiring."""

from __future__ import annotations

from typing import Optional

import strawberry

from fastapi import HTTPException

from src.auth.dependencies import check_role, get_current_user
from src.db.session import AsyncSessionLocal

from . import resolvers as r
from . import types as t


async def _require_auth(info: strawberry.types.Info, required_role: str = "viewer") -> dict:
    """Extract auth from Strawberry info context and enforce role."""
    request = info.context.get("request") if isinstance(info.context, dict) else getattr(info.context, "request", None)
    if request is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = await get_current_user(request)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    if not check_role(user, required_role):
        raise HTTPException(status_code=403, detail=f"Role '{required_role}' required")
    return user


@strawberry.type
class Query:
    @strawberry.field
    async def element(self, sha256: str) -> t.Element | None:
        async with AsyncSessionLocal() as session:
            return await r.resolve_element(session, sha256)

    @strawberry.field
    async def schema_(self, sha256: str) -> t.Schema | None:
        async with AsyncSessionLocal() as session:
            return await r.resolve_schema(session, sha256)

    @strawberry.field
    async def value(self, sha256: str) -> t.Value | None:
        async with AsyncSessionLocal() as session:
            return await r.resolve_value(session, sha256)

    @strawberry.field
    async def valueset(self, sha256: str) -> t.ValueSet | None:
        async with AsyncSessionLocal() as session:
            return await r.resolve_valueset(session, sha256)

    @strawberry.field
    async def browse_elements(
        self,
        source: Optional[str] = None,
        data_type: Optional[t.DataType] = None,
        has_annotations: Optional[bool] = None,
        search_text: Optional[str] = None,
        first: int = 20,
        after: Optional[str] = None,
    ) -> t.ElementConnection:
        async with AsyncSessionLocal() as session:
            return await r.resolve_browse_elements(
                session, source, data_type, has_annotations, search_text, first, after
            )

    @strawberry.field
    async def browse_schemas(
        self,
        source: Optional[str] = None,
        search_text: Optional[str] = None,
        first: int = 20,
        after: Optional[str] = None,
    ) -> t.SchemaConnection:
        async with AsyncSessionLocal() as session:
            return await r.resolve_browse_schemas(session, source, search_text, first, after)

    @strawberry.field
    async def browse_values(
        self,
        source: Optional[str] = None,
        search_text: Optional[str] = None,
        first: int = 20,
        after: Optional[str] = None,
    ) -> t.ValueConnection:
        async with AsyncSessionLocal() as session:
            return await r.resolve_browse_values(session, source, search_text, first, after)

    @strawberry.field
    async def browse_valuesets(
        self,
        source: Optional[str] = None,
        search_text: Optional[str] = None,
        first: int = 20,
        after: Optional[str] = None,
    ) -> t.ValueSetConnection:
        async with AsyncSessionLocal() as session:
            return await r.resolve_browse_valuesets(session, source, search_text, first, after)

    @strawberry.field
    async def transform(self, sha256: str) -> t.Transform | None:
        async with AsyncSessionLocal() as session:
            return await r.resolve_transform(session, sha256)

    @strawberry.field
    async def browse_transforms(
        self,
        source_element: Optional[str] = None,
        target_element: Optional[str] = None,
        function_type: Optional[str] = None,
        first: int = 20,
        after: Optional[str] = None,
    ) -> t.TransformConnection:
        async with AsyncSessionLocal() as session:
            return await r.resolve_browse_transforms(
                session, source_element, target_element, function_type, first, after
            )

    @strawberry.field
    async def curation_queue(
        self,
        flag_type: Optional[t.FlagType] = None,
        status: Optional[t.FlagStatus] = None,
        first: int = 20,
        after: Optional[str] = None,
    ) -> t.CurationFlagConnection:
        async with AsyncSessionLocal() as session:
            return await r.resolve_curation_queue(session, flag_type, status, first, after)

    @strawberry.field
    async def run_summaries(
        self,
        source: Optional[str] = None,
        first: int = 20,
        after: Optional[str] = None,
    ) -> t.RunSummaryConnection:
        async with AsyncSessionLocal() as session:
            return await r.resolve_run_summaries(session, source, first, after)

    @strawberry.field
    async def latest_run(self, source: Optional[str] = None) -> t.RunSummary | None:
        async with AsyncSessionLocal() as session:
            return await r.resolve_latest_run(session, source)

    @strawberry.field
    async def ontology_sources(self, active: Optional[bool] = None) -> list[t.OntologySourceType]:
        async with AsyncSessionLocal() as session:
            return await r.resolve_ontology_sources(session, active)

    @strawberry.field
    async def ingestion_queue(self, status: Optional[str] = None, first: int = 50) -> list[t.IngestionJobType]:
        async with AsyncSessionLocal() as session:
            return await r.resolve_ingestion_queue(session, status, first)

    @strawberry.field
    async def enrichment_proposals(
        self,
        entity_type: Optional[str] = None,
        entity_ref: Optional[str] = None,
        status: Optional[str] = None,
        first: int = 50,
    ) -> list[t.LLMEnrichmentProposalType]:
        async with AsyncSessionLocal() as session:
            return await r.resolve_enrichment_proposals(session, entity_type, entity_ref, status, first)


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def resolve_flag(self, info: strawberry.types.Info, input: t.ResolveFlagInput) -> t.CurationFlag:
        user = await _require_auth(info, "curator")
        async with AsyncSessionLocal() as session:
            # Override resolved_by with authenticated user's name
            input_with_user = t.ResolveFlagInput(
                flag_id=input.flag_id,
                action=input.action,
                resolved_by=user.get("name", user.get("sub", "unknown")),
                note=input.note,
            )
            result = await r.resolve_resolve_flag(session, input_with_user)
            await session.commit()
            return result

    @strawberry.mutation
    async def batch_resolve_flags(self, info: strawberry.types.Info, input: t.BatchResolveFlagInput) -> list[t.CurationFlag]:
        user = await _require_auth(info, "curator")
        async with AsyncSessionLocal() as session:
            input_with_user = t.BatchResolveFlagInput(
                flag_ids=input.flag_ids,
                action=input.action,
                resolved_by=user.get("name", user.get("sub", "unknown")),
                note=input.note,
            )
            results = await r.resolve_batch_resolve_flags(session, input_with_user)
            await session.commit()
            return results

    @strawberry.mutation
    async def submit_contribution(self, info: strawberry.types.Info, input: t.SubmitContributionInput) -> t.Contribution:
        user = await _require_auth(info, "contributor")
        # Override contributor with authenticated user
        input_with_user = t.SubmitContributionInput(
            entity_type=input.entity_type,
            entity_ref=input.entity_ref,
            contribution_type=input.contribution_type,
            content=input.content,
            contributor=user.get("name", user.get("sub", "unknown")),
        )
        async with AsyncSessionLocal() as session:
            result = await r.resolve_submit_contribution(session, input_with_user)
            await session.commit()
            return result

    @strawberry.mutation
    async def approve_annotation(
        self,
        info: strawberry.types.Info,
        entity_sha256: str,
        annotation_index: int,
    ) -> t.Element:
        """Approve an ontology annotation — moves it to curated_annotations (protected from re-enrichment)."""
        user = await _require_auth(info, "curator")
        async with AsyncSessionLocal() as session:
            result = await r.resolve_approve_annotation(
                session, entity_sha256, annotation_index, user.get("name", "unknown")
            )
            await session.commit()
            return result

    @strawberry.mutation
    async def reject_annotation(
        self,
        info: strawberry.types.Info,
        entity_sha256: str,
        annotation_index: int,
        reason: Optional[str] = None,
    ) -> t.Element:
        """Reject an ontology annotation — removes it and records the rejection."""
        user = await _require_auth(info, "curator")
        async with AsyncSessionLocal() as session:
            result = await r.resolve_reject_annotation(
                session, entity_sha256, annotation_index, user.get("name", "unknown"), reason
            )
            await session.commit()
            return result

    @strawberry.mutation
    async def import_registry(self, info: strawberry.types.Info, registry_path: str) -> t.ImportResult:
        await _require_auth(info, "admin")
        async with AsyncSessionLocal() as session:
            result = await r.resolve_import_registry(session, registry_path)
            await session.commit()
            return result


    @strawberry.mutation
    async def update_element(self, info: strawberry.types.Info, sha256: str, input: t.UpdateElementInput) -> t.Element | None:
        user = await _require_auth(info, "curator")
        updates = {k: v for k, v in {
            "data_type": input.data_type, "unit": input.unit, "unit_uri": input.unit_uri,
            "description": input.description, "pattern": input.pattern,
            "value_domain": input.value_domain, "min_value": input.min_value,
            "max_value": input.max_value, "type_ref": input.type_ref,
            "ontology_annotations": input.ontology_annotations,
        }.items() if v is not None}
        async with AsyncSessionLocal() as session:
            row = await r.resolve_update_entity(
                session, "elements", sha256, updates, input.reason,
                user.get("name", user.get("sub", "unknown")),
            )
            if row is None:
                raise ValueError(f"Element {sha256} not found")
            await session.commit()
            return r._element_from_row(row)

    @strawberry.mutation
    async def update_schema(self, info: strawberry.types.Info, sha256: str, input: t.UpdateSchemaInput) -> t.Schema | None:
        user = await _require_auth(info, "curator")
        updates = {k: v for k, v in {
            "description": input.description, "subclass_of": input.subclass_of,
            "is_mixin": input.is_mixin, "properties": input.properties,
            "ontology_annotations": input.ontology_annotations,
        }.items() if v is not None}
        async with AsyncSessionLocal() as session:
            row = await r.resolve_update_entity(
                session, "schemas", sha256, updates, input.reason,
                user.get("name", user.get("sub", "unknown")),
            )
            if row is None:
                raise ValueError(f"Schema {sha256} not found")
            await session.commit()
            return r._schema_from_row(row)

    @strawberry.mutation
    async def update_value(self, info: strawberry.types.Info, sha256: str, input: t.UpdateValueInput) -> t.Value | None:
        user = await _require_auth(info, "curator")
        updates = {k: v for k, v in {
            "label": input.label, "value_type": input.value_type,
            "description": input.description, "ontology_id": input.ontology_id,
            "ontology_annotations": input.ontology_annotations,
        }.items() if v is not None}
        async with AsyncSessionLocal() as session:
            row = await r.resolve_update_entity(
                session, "values", sha256, updates, input.reason,
                user.get("name", user.get("sub", "unknown")),
            )
            if row is None:
                raise ValueError(f"Value {sha256} not found")
            await session.commit()
            return r._value_from_row(row)


schema = strawberry.Schema(query=Query, mutation=Mutation)
