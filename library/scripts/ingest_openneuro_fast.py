"""Batch ingest of OpenNeuro datasets using datalad for annex file retrieval.

OpenNeuro datasets use git-annex — plain git clone only gets pointer files.
Must use datalad install + get to retrieve actual TSV/JSON content.

Usage:
    uv run python scripts/ingest_openneuro_fast.py --max 100
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import subprocess
import tempfile
import time
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

OUTPUT_DIR = Path.home() / ".cache" / "undata" / "registry"


def get_dataset_ids(max_datasets: int = 100) -> list[str]:
    """Fetch dataset IDs from OpenNeuro GraphQL API."""
    import httpx
    resp = httpx.post("https://openneuro.org/crn/graphql", json={
        "query": f"""
        {{
          datasets(first: {max_datasets}, orderBy: {{created: descending}}) {{
            edges {{ node {{ id }} }}
          }}
        }}
        """
    }, timeout=30)
    return [e["node"]["id"] for e in resp.json()["data"]["datasets"]["edges"]]


def clone_and_get(dataset_id: str, dest: Path, timeout: int = 120) -> bool:
    """Clone via git (with annex branches) then use datalad get for metadata files.

    Strategy: git clone (fast, gets annex branch refs) → datalad get (fetches actual file content).
    """
    url = f"https://github.com/OpenNeuroDatasets/{dataset_id}.git"
    try:
        # Step 1: git clone (fetches all branches including git-annex)
        subprocess.run(
            ["git", "clone", "--single-branch", url, str(dest)],
            check=True, capture_output=True, timeout=timeout,
        )

        # Step 2: init git-annex so datalad can fetch content
        subprocess.run(
            ["git", "-C", str(dest), "annex", "init"],
            check=False, capture_output=True, timeout=30,
        )

        # Step 3: datalad get for metadata files
        for pattern in ["*.tsv", "*.json", "phenotype/*.tsv", "phenotype/*.json"]:
            try:
                subprocess.run(
                    ["datalad", "get", "-d", str(dest), pattern],
                    check=False, capture_output=True, timeout=60,
                )
            except subprocess.TimeoutExpired:
                pass

        return True
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as e:
        logger.debug("Clone failed for %s: %s", dataset_id, e)
        return False
    except FileNotFoundError:
        logger.warning("git or datalad not found in PATH")
        return False


def extract_from_dataset(dataset_path: Path, dataset_id: str) -> list[dict]:
    """Extract entities from a cloned dataset directory."""
    from undata_library.adapters.openneuro import OpenNeuroAdapter
    adapter = OpenNeuroAdapter()
    try:
        entities = adapter.extract(dataset_path)
        return [
            {
                "entity_type": e.entity_type.value,
                "semantic": e.semantic,
                "provenance": e.provenance,
            }
            for e in entities
        ]
    except Exception as e:
        logger.warning("Extract failed for %s: %s", dataset_id, e)
        return []


def write_entities(entities: list[dict], output_dir: Path):
    """Write entities to registry YAML files."""
    type_dirs = {"attribute": "elements", "class": "schemas",
                 "enum_value": "values", "valueset": "valuesets"}
    for entity in entities:
        dir_name = type_dirs.get(entity["entity_type"], "elements")
        entity_dir = output_dir / dir_name
        entity_dir.mkdir(parents=True, exist_ok=True)

        data = {"semantic": entity["semantic"], "provenance": [entity["provenance"]]}
        content = json.dumps(data, sort_keys=True, default=str)
        short_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        name = entity["provenance"].get("name", "unknown")
        safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in name)[:40]
        filename = f"{safe_name}_{short_hash}.yaml"

        (entity_dir / filename).write_text(
            yaml.dump(data, default_flow_style=False, sort_keys=False), encoding="utf-8")


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max", type=int, default=100)
    parser.add_argument("--timeout", type=int, default=120, help="Clone timeout per dataset")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    logger.info("Fetching dataset list...")
    dataset_ids = get_dataset_ids(args.max)
    logger.info("Found %d datasets", len(dataset_ids))

    tmp_base = Path(tempfile.mkdtemp(prefix="on-batch-"))
    total_entities = 0
    successful = 0
    failed = 0
    skipped = 0
    t0 = time.time()

    for i, did in enumerate(dataset_ids):
        t1 = time.time()
        dest = tmp_base / did
        logger.info("[%d/%d] %s", i + 1, len(dataset_ids), did)

        if not clone_and_get(did, dest, timeout=args.timeout):
            failed += 1
            logger.info("  → clone failed (%.0fs)", time.time() - t1)
            shutil.rmtree(dest, ignore_errors=True)
            continue

        entities = extract_from_dataset(dest, did)
        shutil.rmtree(dest, ignore_errors=True)

        if not entities:
            skipped += 1
            logger.info("  → no metadata (%.0fs)", time.time() - t1)
            continue

        write_entities(entities, OUTPUT_DIR)
        total_entities += len(entities)
        successful += 1
        logger.info("  → %d entities (%.0fs)", len(entities), time.time() - t1)

    elapsed = time.time() - t0

    runs_dir = OUTPUT_DIR / "runs"
    runs_dir.mkdir(exist_ok=True)
    ts = time.strftime("%Y-%m-%dT%H-%M-%S")
    summary = {
        "source": "openneuro-batch",
        "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "datasets_attempted": len(dataset_ids),
        "datasets_successful": successful,
        "datasets_failed": failed,
        "datasets_skipped": skipped,
        "total_entities": total_entities,
        "elapsed_seconds": round(elapsed, 1),
    }
    (runs_dir / f"{ts}-openneuro-batch.yaml").write_text(
        yaml.dump(summary, default_flow_style=False), encoding="utf-8")

    shutil.rmtree(tmp_base, ignore_errors=True)

    logger.info("\n=== BATCH COMPLETE ===")
    logger.info("Successful: %d | Failed: %d | Skipped: %d | Total: %d",
                successful, failed, skipped, len(dataset_ids))
    logger.info("Entities: %d", total_entities)
    logger.info("Time: %.0fs (%.1fs avg)", elapsed, elapsed / max(len(dataset_ids), 1))


if __name__ == "__main__":
    main()
