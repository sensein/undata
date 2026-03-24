"""Run summary generation and delta comparison for pipeline runs."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from .models import RunSummary
from .utils import safe_load_yaml, write_yaml


def generate_summary(
    run_id: str,
    source: str,
    entity_counts: dict,
    enrichment_rate: dict | None = None,
    curation_flags: dict | None = None,
    timing: dict | None = None,
) -> RunSummary:
    """Create a RunSummary for a completed pipeline run."""
    return RunSummary(
        run_id=run_id,
        source=source,
        started_at=datetime.now(timezone.utc).isoformat(),
        entity_counts=entity_counts,
        enrichment_rate=enrichment_rate,
        curation_flags=curation_flags,
        timing=timing,
    )


def save_summary(output_dir: Path, summary: RunSummary) -> Path:
    """Save a RunSummary to the runs/ directory."""
    runs_dir = output_dir / "runs"
    runs_dir.mkdir(parents=True, exist_ok=True)

    timestamp = summary.started_at.replace(":", "-").replace("+", "p")[:19]
    filename = f"{timestamp}-{summary.source}.yaml"
    filepath = runs_dir / filename

    write_yaml(filepath, summary.model_dump(mode="json", exclude_none=True))
    return filepath


def load_previous_summary(output_dir: Path, source: str) -> RunSummary | None:
    """Load the most recent RunSummary for a given source.

    Returns None if no previous run exists.
    """
    runs_dir = output_dir / "runs"
    if not runs_dir.exists():
        return None

    # Find the latest run file for this source (sorted by filename = timestamp)
    candidates = sorted(runs_dir.glob(f"*-{source}.yaml"), reverse=True)
    if not candidates:
        return None

    data = safe_load_yaml(candidates[0])
    if data is None:
        return None

    try:
        return RunSummary.model_validate(data)
    except Exception:
        return None


def compute_delta(
    current_counts: dict,
    previous_counts: dict,
) -> dict:
    """Compute per-entity-type delta between two run's entity counts.

    Both inputs should be dicts like {elements: N, schemas: N, values: N, valuesets: N}.
    Returns {elements: {added: N, removed: N}, schemas: {...}, ...}
    """
    delta: dict[str, dict[str, int]] = {}
    all_types = set(current_counts.keys()) | set(previous_counts.keys())

    for entity_type in sorted(all_types):
        curr = current_counts.get(entity_type, 0)
        prev = previous_counts.get(entity_type, 0)
        diff = curr - prev
        if diff > 0:
            delta[entity_type] = {"added": diff, "removed": 0}
        elif diff < 0:
            delta[entity_type] = {"added": 0, "removed": abs(diff)}
        else:
            delta[entity_type] = {"added": 0, "removed": 0}

    return delta


def compute_entity_delta(
    current_dir: Path,
    previous_hashes: dict[str, str],
) -> dict[str, list[str]]:
    """Compare individual entity files against previous run's hash map.

    previous_hashes: {filename: sha256} from the previous run.
    Returns: {added: [filenames], removed: [filenames], modified: [filenames]}
    """
    current_files: dict[str, str] = {}
    for f in sorted(current_dir.glob("*.yaml")):
        data = safe_load_yaml(f)
        if data and "sha256" in data:
            current_files[f.name] = data["sha256"]

    current_names = set(current_files.keys())
    previous_names = set(previous_hashes.keys())

    added = sorted(current_names - previous_names)
    removed = sorted(previous_names - current_names)
    modified = sorted(
        name
        for name in current_names & previous_names
        if current_files[name] != previous_hashes[name]
    )

    return {"added": added, "removed": removed, "modified": modified}
