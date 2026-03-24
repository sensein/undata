"""Pipeline service — wraps undata-library for server-side pipeline operations.

The backend uses the library as its ingestion/enrichment/alignment engine.
All pipeline operations go through the library, then results are stored in
the database for fast GraphQL querying.
"""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def run_pipeline(
    session: AsyncSession,
    source: str,
    output_dir: Path | None = None,
    skip_enrich: bool = False,
    skip_align: bool = False,
    use_llm: bool = False,
) -> dict:
    """Run the full library pipeline for a source and import results to DB.

    Flow:
    1. Library: extract → staging (UUID files)
    2. Library: enrich (source metadata + embedding + optional LLM)
    3. Library: commit (content-addressed hash → registry)
    4. Library: align (cross-source annotation transfer)
    5. Library: generate curation flags
    6. Service: import committed registry to database

    Returns pipeline stats.
    """
    import asyncio

    from undata_library.commit import commit_staged
    from undata_library.cross_align import cross_source_align
    from undata_library.enrich import enrich_all, generate_curation_flags
    from undata_library.ingest import ingest_source
    from undata_library.staging import create_staging_dir, generate_run_id
    from undata_library.transform import flag_unknown_transforms

    # Determine output directory
    if output_dir is None:
        from undata_library.models import RegistryConfig

        output_dir = RegistryConfig.resolve()

    cache_dir = Path.home() / ".cache" / "undata"
    run_id = generate_run_id()
    staging = create_staging_dir(output_dir, run_id)

    # Run pipeline in thread pool (library functions are sync)
    def _run_sync():
        stats = {}

        # Extract
        ingest_stats = ingest_source(source, None, staging)
        stats["extract"] = ingest_stats

        # Enrich
        if not skip_enrich:
            enrich_stats = enrich_all(
                staging_dir=staging,
                cache_dir=cache_dir,
                use_llm=use_llm,
            )
            stats["enrich"] = enrich_stats

        # Commit
        commit_stats = commit_staged(staging, output_dir)
        stats["commit"] = commit_stats

        # Align
        if not skip_align:
            align_stats = cross_source_align(output_dir)
            stats["align"] = align_stats

        # Curation flags
        flags = generate_curation_flags(staging_dir=output_dir, output_dir=output_dir)
        transform_flags = flag_unknown_transforms(
            transforms_dir=output_dir / "transforms", output_dir=output_dir
        )
        stats["flags"] = len(flags) + len(transform_flags)

        return stats

    stats = await asyncio.to_thread(_run_sync)

    # Import results to database
    from .import_service import import_registry

    import_stats = await import_registry(session, output_dir, clear_existing=False)
    stats["db_import"] = import_stats

    return stats


async def refresh_ontology(session: AsyncSession) -> dict:
    """Refresh the ontology store from configured sources."""
    import asyncio

    def _run_sync():
        from undata_library.ontology_store import OntologyStore, load_ontology_config

        store_path = Path.home() / ".cache" / "undata" / "ontology-store"
        store = OntologyStore(store_path)
        config = load_ontology_config()

        loaded = 0
        for entry in config:
            if entry.get("disabled"):
                continue
            try:
                name = entry["name"]
                url = entry["url"]
                fmt = entry.get("format", "obo")
                # Download and load — library handles this
                from undata_library.ontology_fetch import download_obo

                dl_path = download_obo(name, url)
                if fmt == "obo":
                    store.load_obo(name, dl_path)
                else:
                    store.load_rdf(name, dl_path, fmt)
                loaded += 1
            except Exception as exc:
                logger.warning("Failed to load %s: %s", entry.get("name"), exc)

        return {"loaded": loaded, "total_config": len(config)}

    return await asyncio.to_thread(_run_sync)


async def discover_sources() -> list[dict]:
    """Run source discovery scan using the library."""
    import asyncio

    def _run_sync():
        from undata_library.discovery import scan_for_candidates

        return scan_for_candidates()

    return await asyncio.to_thread(_run_sync)
