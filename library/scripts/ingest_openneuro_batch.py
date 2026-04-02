"""Batch ingest OpenNeuro datasets into the undata registry.

Usage:
    uv run python scripts/ingest_openneuro_batch.py [--max N] [--output-dir DIR]

Clones each dataset via datalad, extracts elements from TSV/CSV + JSON files,
and writes to the registry. Skips datasets that fail to clone or have no metadata.
"""

from __future__ import annotations

import json
import logging
import shutil
import sys
import tempfile
import time
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def get_dataset_ids(max_datasets: int = 100) -> list[str]:
    """Fetch dataset IDs from OpenNeuro GraphQL API."""
    import httpx

    resp = httpx.post("https://openneuro.org/crn/graphql", json={
        "query": f"""
        {{
          datasets(first: {max_datasets}, orderBy: {{created: descending}}) {{
            edges {{
              node {{
                id
              }}
            }}
          }}
        }}
        """
    }, timeout=30)
    data = resp.json()
    return [e["node"]["id"] for e in data["data"]["datasets"]["edges"]]


def clone_and_extract(dataset_id: str, tmp_base: Path) -> tuple[int, list]:
    """Clone a single dataset and extract entities. Returns (entity_count, entities)."""
    from undata_library.adapters.openneuro import OpenNeuroAdapter

    adapter = OpenNeuroAdapter()
    dataset_path = tmp_base / dataset_id

    try:
        # Clone via datalad
        import datalad.api as dl
        url = f"https://github.com/OpenNeuroDatasets/{dataset_id}.git"
        dl.install(source=url, path=str(dataset_path))

        # Fetch metadata files only
        import glob as _glob
        for pattern in ["*.tsv", "*.json", "phenotype/*.tsv", "phenotype/*.json"]:
            matches = list(_glob.glob(str(dataset_path / pattern)))
            if matches:
                try:
                    dl.get(matches, dataset=str(dataset_path))
                except Exception:
                    pass

        # Extract
        entities = adapter.extract(dataset_path)
        return len(entities), entities
    except Exception as e:
        logger.warning("Failed to process %s: %s", dataset_id, e)
        return 0, []
    finally:
        # Clean up clone to save disk space
        if dataset_path.exists():
            shutil.rmtree(dataset_path, ignore_errors=True)


def write_entities_to_staging(entities: list, dataset_id: str, output_dir: Path):
    """Write extracted entities to staging YAML files."""
    import yaml
    from undata_library.models import EntityType

    type_dirs = {
        EntityType.ATTRIBUTE: "elements",
        EntityType.CLASS: "schemas",
        EntityType.ENUM_VALUE: "values",
        EntityType.VALUESET: "valuesets",
    }

    for entity in entities:
        dir_name = type_dirs.get(entity.entity_type, "elements")
        entity_dir = output_dir / dir_name
        entity_dir.mkdir(parents=True, exist_ok=True)

        # Build YAML data
        data = {
            "semantic": entity.semantic,
            "provenance": [entity.provenance],
        }

        # Generate filename from provenance
        prov = entity.provenance
        name = prov.get("name", "unknown")
        source = prov.get("source", dataset_id).replace("/", "_")
        # Simple hash for uniqueness
        import hashlib
        content = json.dumps(data, sort_keys=True, default=str)
        short_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)
        filename = f"{safe_name}_{short_hash}.yaml"

        (entity_dir / filename).write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Batch ingest OpenNeuro datasets")
    parser.add_argument("--max", type=int, default=100, help="Max datasets to process")
    parser.add_argument("--output-dir", type=str, default=None, help="Registry output directory")
    parser.add_argument("--skip-existing", action="store_true", help="Skip if run summary exists")
    args = parser.parse_args()

    output_dir = Path(args.output_dir) if args.output_dir else Path.home() / ".cache" / "undata" / "registry"
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Fetching dataset list from OpenNeuro API...")
    dataset_ids = get_dataset_ids(args.max)
    logger.info("Found %d datasets", len(dataset_ids))

    # Check which datasets are already ingested
    runs_dir = output_dir / "runs"
    existing_sources = set()
    if runs_dir.exists():
        for f in runs_dir.glob("*.yaml"):
            if "openneuro" in f.name.lower():
                # Extract dataset ID from run summary
                import yaml
                try:
                    data = yaml.safe_load(f.read_text())
                    src = data.get("source", "")
                    if src.startswith("openneuro/"):
                        existing_sources.add(src.split("/", 1)[1])
                except Exception:
                    pass

    if args.skip_existing and existing_sources:
        logger.info("Skipping %d already-ingested datasets", len(existing_sources))
        dataset_ids = [d for d in dataset_ids if d not in existing_sources]

    tmp_base = Path(tempfile.mkdtemp(prefix="openneuro-batch-"))
    total_entities = 0
    successful = 0
    failed = 0
    t0 = time.time()

    for i, dataset_id in enumerate(dataset_ids):
        logger.info("[%d/%d] Processing %s...", i + 1, len(dataset_ids), dataset_id)
        t1 = time.time()

        count, entities = clone_and_extract(dataset_id, tmp_base)

        if count > 0:
            write_entities_to_staging(entities, dataset_id, output_dir)
            total_entities += count
            successful += 1
            logger.info("  → %d entities in %.1fs", count, time.time() - t1)
        else:
            failed += 1
            logger.info("  → skipped (no metadata or clone failed) in %.1fs", time.time() - t1)

    elapsed = time.time() - t0
    logger.info("\n=== BATCH COMPLETE ===")
    logger.info("Datasets: %d successful, %d failed, %d total", successful, failed, len(dataset_ids))
    logger.info("Entities: %d total extracted", total_entities)
    logger.info("Time: %.0fs (%.1fs/dataset)", elapsed, elapsed / max(len(dataset_ids), 1))

    # Clean up
    shutil.rmtree(tmp_base, ignore_errors=True)


if __name__ == "__main__":
    main()
