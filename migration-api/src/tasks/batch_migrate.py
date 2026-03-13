"""Async Celery task: batch_migrate."""

from __future__ import annotations

from src.tasks.celery_app import celery_app


@celery_app.task(bind=True, name="tasks.batch_migrate")
def batch_migrate_task(self, request_dict: dict) -> dict:
    """Execute batch record migration asynchronously."""
    import asyncio

    from src.services.backend_client import BackendClient
    from src.services.pathway_executor import PathwayExecutor

    records = request_dict["records"]
    pathway_id = request_dict["pathway_id"]
    results = []

    self.update_state(state="PROGRESS", meta={"progress": 0})

    async def _run():
        async with BackendClient() as client:
            executor = PathwayExecutor(client)
            for i, record in enumerate(records):
                try:
                    report = await executor.execute(pathway_id=pathway_id, input_record=record)
                    results.append(
                        {
                            "input_record": record,
                            "output_record": report.output_record
                            if hasattr(report, "output_record")
                            else {},
                            "status": report.overall_status,
                            "report": {},
                        }
                    )
                except Exception as exc:
                    results.append(
                        {
                            "input_record": record,
                            "output_record": None,
                            "status": "FAIL",
                            "report": {"error": str(exc)},
                        }
                    )
                progress = int((i + 1) / len(records) * 100)
                self.update_state(state="PROGRESS", meta={"progress": progress})
            return results

    all_results = asyncio.run(_run())
    succeeded = sum(1 for r in all_results if r["status"] in ("PASS", "OK"))
    failed = len(all_results) - succeeded
    return {
        "pathway_id": pathway_id,
        "total": len(all_results),
        "succeeded": succeeded,
        "failed": failed,
        "results": all_results,
    }
