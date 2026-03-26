"""Strawberry GraphQL schema — Query + Mutation wiring."""

from __future__ import annotations

from typing import Optional

import strawberry

from src.db.session import AsyncSessionLocal

from . import resolvers as r
from . import types as t


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
    async def curation_queue(
        self,
        flag_type: Optional[t.FlagType] = None,
        status: t.FlagStatus = t.FlagStatus.PENDING,
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


@strawberry.type
class Mutation:
    @strawberry.mutation
    async def resolve_flag(self, input: t.ResolveFlagInput) -> t.CurationFlag:
        async with AsyncSessionLocal() as session:
            result = await r.resolve_resolve_flag(session, input)
            await session.commit()
            return result

    @strawberry.mutation
    async def batch_resolve_flags(self, input: t.BatchResolveFlagInput) -> list[t.CurationFlag]:
        async with AsyncSessionLocal() as session:
            results = await r.resolve_batch_resolve_flags(session, input)
            await session.commit()
            return results

    @strawberry.mutation
    async def submit_contribution(self, input: t.SubmitContributionInput) -> t.Contribution:
        async with AsyncSessionLocal() as session:
            result = await r.resolve_submit_contribution(session, input)
            await session.commit()
            return result

    @strawberry.mutation
    async def import_registry(self, registry_path: str) -> t.ImportResult:
        async with AsyncSessionLocal() as session:
            result = await r.resolve_import_registry(session, registry_path)
            await session.commit()
            return result


schema = strawberry.Schema(query=Query, mutation=Mutation)
