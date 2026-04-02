"""Strawberry GraphQL schema — Query + Mutation wiring."""

from __future__ import annotations

from typing import Optional

import strawberry
from strawberry.scalars import JSON

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
    async def search(
        self,
        query: str,
        mode: Optional[t.SearchMode] = None,
        first: int = 50,
    ) -> list[t.SearchResultType]:
        """Search across all entity types. Mode: LEXICAL, SEMANTIC, or BOTH (default)."""
        async with AsyncSessionLocal() as session:
            return await r.resolve_search(session, query, first, mode=mode.value if mode else "both")

    @strawberry.field
    async def browse_elements(
        self,
        source: Optional[str] = None,
        data_type: Optional[t.DataType] = None,
        has_annotations: Optional[bool] = None,
        search_text: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        first: int = 20,
        after: Optional[str] = None,
    ) -> t.ElementConnection:
        async with AsyncSessionLocal() as session:
            return await r.resolve_browse_elements(
                session, source, data_type, has_annotations, search_text, first, after,
                sort_by=sort_by, sort_order=sort_order,
            )

    @strawberry.field
    async def browse_schemas(
        self,
        source: Optional[str] = None,
        search_text: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        first: int = 20,
        after: Optional[str] = None,
    ) -> t.SchemaConnection:
        async with AsyncSessionLocal() as session:
            return await r.resolve_browse_schemas(
                session, source, search_text, first, after,
                sort_by=sort_by, sort_order=sort_order,
            )

    @strawberry.field
    async def browse_values(
        self,
        source: Optional[str] = None,
        search_text: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        first: int = 20,
        after: Optional[str] = None,
    ) -> t.ValueConnection:
        async with AsyncSessionLocal() as session:
            return await r.resolve_browse_values(
                session, source, search_text, first, after,
                sort_by=sort_by, sort_order=sort_order,
            )

    @strawberry.field
    async def browse_valuesets(
        self,
        source: Optional[str] = None,
        search_text: Optional[str] = None,
        sort_by: Optional[str] = None,
        sort_order: Optional[str] = None,
        first: int = 20,
        after: Optional[str] = None,
    ) -> t.ValueSetConnection:
        async with AsyncSessionLocal() as session:
            return await r.resolve_browse_valuesets(
                session, source, search_text, first, after,
                sort_by=sort_by, sort_order=sort_order,
            )

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
    async def schemas_using_element(self, sha256: str, first: int = 50) -> t.SchemaConnection:
        """Find schemas whose properties[] array contains the given element sha256."""
        async with AsyncSessionLocal() as session:
            return await r.resolve_schemas_using_element(session, sha256, first)

    @strawberry.field
    async def transforms_for_element(self, sha256: str, first: int = 50) -> t.TransformConnection:
        """Find transforms where source_element or target_element matches."""
        async with AsyncSessionLocal() as session:
            return await r.resolve_transforms_for_element(session, sha256, first)

    @strawberry.field
    async def flags_for_entity(
        self, entity_type: str, entity_ref: str, first: int = 50
    ) -> t.CurationFlagConnection:
        """Find curation flags for a specific entity."""
        async with AsyncSessionLocal() as session:
            return await r.resolve_flags_for_entity(session, entity_type, entity_ref, first)

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

    @strawberry.field
    async def ontology_store_info(self) -> list[t.OntologyStoreEntry]:
        """Read loaded ontologies from pyoxigraph store or DB fallback."""
        async with AsyncSessionLocal() as session:
            raw = await r.resolve_ontology_store_info(session)
        return [
            t.OntologyStoreEntry(
                name=e["name"],
                display_name=e["display_name"],
                term_count=e["term_count"],
                format=e.get("format", ""),
                checksum=e.get("checksum", ""),
                last_refreshed=e.get("last_refreshed", ""),
            )
            for e in raw
        ]

    @strawberry.field
    async def audit_log(
        self,
        entity_type: Optional[str] = None,
        entity_ref: Optional[str] = None,
        agent: Optional[str] = None,
        activity: Optional[str] = None,
        first: int = 50,
    ) -> list[t.AuditLogEntry]:
        """Query audit log entries with optional filters."""
        async with AsyncSessionLocal() as session:
            return await r.resolve_audit_log(session, entity_type, entity_ref, agent, activity, first)


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def resolve_flag(self, info: strawberry.types.Info, input: t.ResolveFlagInput) -> t.CurationFlag:
        user = await _require_auth(info, "curator")
        async with AsyncSessionLocal() as session:
            from src.services.audit_service import write_audit
            curator = user.get("name", user.get("sub", "unknown"))
            input_with_user = t.ResolveFlagInput(
                flag_id=input.flag_id,
                action=input.action,
                resolved_by=curator,
                note=input.note,
            )
            result = await r.resolve_resolve_flag(session, input_with_user)
            await write_audit(
                session, activity=f"flag_{input.action.value}", agent=curator,
                entity_type="flag", entity_ref=str(input.flag_id),
                details={"note": input.note},
            )
            await session.commit()
            return result

    @strawberry.mutation
    async def batch_resolve_flags(self, info: strawberry.types.Info, input: t.BatchResolveFlagInput) -> list[t.CurationFlag]:
        user = await _require_auth(info, "curator")
        async with AsyncSessionLocal() as session:
            from src.services.audit_service import write_audit
            curator = user.get("name", user.get("sub", "unknown"))
            input_with_user = t.BatchResolveFlagInput(
                flag_ids=input.flag_ids,
                action=input.action,
                resolved_by=curator,
                note=input.note,
            )
            results = await r.resolve_batch_resolve_flags(session, input_with_user)
            for fid in input.flag_ids:
                await write_audit(
                    session, activity=f"flag_{input.action.value}", agent=curator,
                    entity_type="flag", entity_ref=str(fid),
                    details={"note": input.note, "batch": True},
                )
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
            from src.services.audit_service import write_audit
            curator = user.get("name", "unknown")
            result = await r.resolve_approve_annotation(session, entity_sha256, annotation_index, curator)
            await write_audit(
                session, activity="approve_annotation", agent=curator,
                entity_type="element", entity_ref=entity_sha256,
                details={"annotation_index": annotation_index},
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
            from src.services.audit_service import write_audit
            curator = user.get("name", "unknown")
            result = await r.resolve_reject_annotation(session, entity_sha256, annotation_index, curator, reason)
            await write_audit(
                session, activity="reject_annotation", agent=curator,
                entity_type="element", entity_ref=entity_sha256,
                details={"annotation_index": annotation_index, "reason": reason},
            )
            await session.commit()
            return result

    @strawberry.mutation
    async def import_registry(self, info: strawberry.types.Info, registry_path: str) -> t.ImportResult:
        user = await _require_auth(info, "admin")
        async with AsyncSessionLocal() as session:
            from src.services.audit_service import write_audit
            result = await r.resolve_import_registry(session, registry_path)
            agent = user.get("name", user.get("sub", "system"))
            await write_audit(
                session, activity="import", agent=agent,
                entity_type="registry", entity_ref=registry_path,
                details={"elements": result.elements, "schemas": result.schemas},
            )
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
            from src.services.audit_service import write_audit
            curator = user.get("name", user.get("sub", "unknown"))
            row = await r.resolve_update_entity(session, "elements", sha256, updates, input.reason, curator)
            if row is None:
                raise ValueError(f"Element {sha256} not found")
            await write_audit(
                session, activity="update", agent=curator,
                entity_type="element", entity_ref=sha256,
                details={"reason": input.reason, "fields": list(updates.keys())},
            )
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
            from src.services.audit_service import write_audit
            curator = user.get("name", user.get("sub", "unknown"))
            row = await r.resolve_update_entity(session, "schemas", sha256, updates, input.reason, curator)
            if row is None:
                raise ValueError(f"Schema {sha256} not found")
            await write_audit(
                session, activity="update", agent=curator,
                entity_type="schema", entity_ref=sha256,
                details={"reason": input.reason, "fields": list(updates.keys())},
            )
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
            from src.services.audit_service import write_audit
            curator = user.get("name", user.get("sub", "unknown"))
            row = await r.resolve_update_entity(session, "values", sha256, updates, input.reason, curator)
            if row is None:
                raise ValueError(f"Value {sha256} not found")
            await write_audit(
                session, activity="update", agent=curator,
                entity_type="value", entity_ref=sha256,
                details={"reason": input.reason, "fields": list(updates.keys())},
            )
            await session.commit()
            return r._value_from_row(row)

    # --- T022: Element Versioning ---

    @strawberry.mutation
    async def version_element(
        self,
        info: strawberry.types.Info,
        sha256: str,
        changes: JSON,
        reason: Optional[str] = None,
    ) -> t.Element:
        """Create a new version of an element with changed semantic fields."""
        user = await _require_auth(info, "curator")
        curator = user.get("name", user.get("sub", "unknown"))
        async with AsyncSessionLocal() as session:
            from src.services.audit_service import write_audit
            result = await r.resolve_version_element(session, sha256, changes, curator)
            await write_audit(
                session, activity="version", agent=curator,
                entity_type="element", entity_ref=sha256,
                generated_entity_ref=result.sha256,
                details={"changes": changes, "reason": reason},
            )
            await session.commit()
            return result

    # --- T034-T035: Ingestion Approval/Rejection ---

    @strawberry.mutation
    async def approve_ingestion(self, info: strawberry.types.Info, id: strawberry.ID) -> t.IngestionJobType:
        """Approve an ingestion job — sets status to 'approved' and records approver."""
        user = await _require_auth(info, "curator")
        approver = user.get("name", user.get("sub", "unknown"))
        async with AsyncSessionLocal() as session:
            from src.services.audit_service import write_audit
            result = await r.resolve_approve_ingestion(session, str(id), approver)
            await write_audit(
                session, activity="approve_ingestion", agent=approver,
                entity_type="ingestion_job", entity_ref=str(id),
            )
            await session.commit()
            return result

    @strawberry.mutation
    async def reject_ingestion(
        self,
        info: strawberry.types.Info,
        id: strawberry.ID,
        reason: Optional[str] = None,
    ) -> t.IngestionJobType:
        """Reject an ingestion job — sets status to 'rejected' and records reason."""
        user = await _require_auth(info, "curator")
        rejector = user.get("name", user.get("sub", "unknown"))
        async with AsyncSessionLocal() as session:
            from src.services.audit_service import write_audit
            result = await r.resolve_reject_ingestion(session, str(id), rejector, reason)
            await write_audit(
                session, activity="reject_ingestion", agent=rejector,
                entity_type="ingestion_job", entity_ref=str(id),
                details={"reason": reason},
            )
            await session.commit()
            return result

    # --- T039-T040: Enrichment Request & Proposal Review ---

    @strawberry.mutation
    async def request_enrichment(
        self,
        info: strawberry.types.Info,
        entity_type: str,
        entity_ref: str,
    ) -> t.LLMEnrichmentProposalType:
        """Request LLM enrichment for an entity — calls suggest_ontology_annotation."""
        await _require_auth(info, "curator")
        async with AsyncSessionLocal() as session:
            result = await r.resolve_request_enrichment(session, entity_type, entity_ref)
            await session.commit()
            return result

    @strawberry.mutation
    async def review_proposal(
        self,
        info: strawberry.types.Info,
        id: strawberry.ID,
        decision: str,
        reason: Optional[str] = None,
    ) -> t.LLMEnrichmentProposalType:
        """Approve or reject an LLM enrichment proposal."""
        user = await _require_auth(info, "curator")
        reviewer = user.get("name", user.get("sub", "unknown"))
        async with AsyncSessionLocal() as session:
            from src.services.audit_service import write_audit
            result = await r.resolve_review_proposal(session, str(id), decision, reviewer, reason)
            await write_audit(
                session, activity=f"proposal_{decision}", agent=reviewer,
                entity_type="proposal", entity_ref=str(id),
                details={"reason": reason},
            )
            await session.commit()
            return result


    # --- T015: Export Registry ---

    @strawberry.mutation
    async def export_registry(
        self, info: strawberry.types.Info, version: Optional[str] = None
    ) -> t.ExportResultType:
        """Export the full registry to YAML + embeddings."""
        await _require_auth(info, "admin")
        from src.core.config import settings
        from src.services.export_service import export_full_registry

        async with AsyncSessionLocal() as session:
            result = await export_full_registry(session, settings.export_dir, version=version)
            return t.ExportResultType(
                version=result["version"],
                file_path=result["file_path"],
                file_size=result["file_size"],
                entity_counts=result["entity_counts"],
                manifest=result["manifest"],
            )

    # --- Version dependency check ---

    @strawberry.mutation
    async def check_dependency_versions(self, info: strawberry.types.Info) -> JSON:
        """Check all registered ontologies/sources for version changes."""
        await _require_auth(info, "admin")
        from src.services.version_service import check_dependency_versions
        async with AsyncSessionLocal() as session:
            transitions = await check_dependency_versions(session)
            await session.commit()
            return transitions

    # --- T025-T026: Releases ---

    @strawberry.field
    async def releases(self, release_type: Optional[str] = None) -> list[t.ReleaseType]:
        async with AsyncSessionLocal() as session:
            return await r.resolve_releases(session, release_type)

    @strawberry.mutation
    async def tag_release(self, info: strawberry.types.Info, version: str) -> t.ReleaseType:
        """Tag the latest nightly export as a versioned release."""
        await _require_auth(info, "admin")
        async with AsyncSessionLocal() as session:
            result = await r.resolve_tag_release(session, version)
            await session.commit()
            return result


schema = strawberry.Schema(query=Query, mutation=Mutation)
