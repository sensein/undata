"""Async Celery task: build_schema."""

from __future__ import annotations

from src.tasks.celery_app import celery_app


@celery_app.task(bind=True, name="tasks.build_schema")
def build_schema_task(self, request_dict: dict) -> dict:
    """Build a LinkML schema asynchronously."""
    import asyncio

    from src.services.backend_client import BackendClient
    from src.services.schema_builder import SchemaBuilder

    self.update_state(state="PROGRESS", meta={"progress": 0})

    async def _run():
        async with BackendClient() as client:
            builder = SchemaBuilder(client)
            self.update_state(state="PROGRESS", meta={"progress": 10})
            result = await builder.build(
                name=request_dict["name"],
                version=request_dict.get("version", "2026.03.0"),
                classes=request_dict["classes"],
            )
            self.update_state(state="PROGRESS", meta={"progress": 100})
            return result

    return asyncio.run(_run())
