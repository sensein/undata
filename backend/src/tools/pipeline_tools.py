"""Pipeline trigger tool for LLM — runs ingestion on new sources."""

from __future__ import annotations

import asyncio


async def trigger_ingestion(source_url: str, adapter_pattern: str) -> dict:
    """Trigger pipeline ingestion. Results are staged for review."""
    try:
        import tempfile
        from pathlib import Path

        from undata_library.ingest import ingest_source

        with tempfile.TemporaryDirectory() as tmpdir:
            stats = await asyncio.to_thread(
                ingest_source,
                adapter_pattern,
                Path(source_url) if "/" in source_url else None,
                Path(tmpdir),
            )

        return {
            "success": True,
            "stats": stats,
            "staged_entities": sum(
                stats.get(k, 0)
                for k in ["created", "schemas_created", "values_created", "valuesets_created"]
            ),
        }
    except Exception as e:
        return {"success": False, "stats": {}, "staged_entities": 0, "error": str(e)}
