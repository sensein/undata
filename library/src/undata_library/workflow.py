"""Parameterizable ingestion workflow engine."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path

from .models import IngestionReport, IngestionViolation, WorkflowSpec
from .utils import safe_load_yaml


def load_workflow(path: Path) -> WorkflowSpec:
    """Load workflow spec from YAML file."""
    data = safe_load_yaml(path)
    if data is None:
        raise ValueError(f"Invalid or missing workflow file: {path}")
    return WorkflowSpec.model_validate(data)


def run_workflow(
    spec: WorkflowSpec,
    library_path: Path,
) -> IngestionReport:
    """Execute a workflow: resolve adapters → extract → route → validate → report."""
    from .adapters.registry import get_default_registry
    from .ingest import ingest_source

    registry = get_default_registry()
    report = IngestionReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        workflow=None,
    )

    total_stats: dict = {
        "elements_created": 0,
        "elements_merged": 0,
        "schemas_created": 0,
        "valuesets_created": 0,
        "values_created": 0,
    }

    for source_spec in spec.sources:
        step_start = time.time()
        source_path = Path(source_spec.path)
        adapter_name = source_spec.adapter

        # Auto-detect adapter if not specified
        if not adapter_name:
            try:
                adapter = registry.auto_detect(source_path)
                adapter_name = adapter.name
            except ValueError:
                report.violations.append(
                    IngestionViolation(
                        file=str(source_path),
                        entity_type="source",
                        check="adapter_detection",
                        message=f"Cannot auto-detect adapter for {source_path}",
                    )
                )
                continue

        try:
            stats = ingest_source(adapter_name, source_path, library_path)
            total_stats["elements_created"] += stats.get("created", 0)
            total_stats["elements_merged"] += stats.get("merged", 0)
            total_stats["schemas_created"] += stats.get("schemas_created", 0)
            total_stats["values_created"] += stats.get("values_created", 0)
        except Exception as exc:
            report.violations.append(
                IngestionViolation(
                    file=str(source_path),
                    entity_type="source",
                    check="ingestion",
                    message=f"Ingestion failed: {exc}",
                )
            )

        step_end = time.time()
        # Record step timing (FR-022)
        total_stats.setdefault("step_timings", []).append(
            {
                "source": str(source_path),
                "adapter": adapter_name,
                "start_time": step_start,
                "end_time": step_end,
                "elapsed_seconds": round(step_end - step_start, 2),
            }
        )

    report.sources_processed = len(spec.sources)
    report.stats = total_stats

    # Run validation unless disabled
    if spec.validation.checks or not spec.validation.strict:
        from .validation import validate_ingestion_output

        violations = validate_ingestion_output(library_path)
        for v in violations:
            report.violations.append(IngestionViolation(**v))

    report.validation_passed = len(report.violations) == 0
    return report
