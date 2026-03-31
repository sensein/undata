"""OpenNeuro adapter — extract elements from BIDS datasets via datalad.

Scans each dataset for CSV/TSV files (participants.tsv, phenotype/*.tsv, etc.)
and their corresponding JSON sidecars. Extracts elements from column headers
with data types inferred from values.
"""

from __future__ import annotations

import csv
import json
import logging
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from ..models import SourceRef
from .base import BaseAdapter, ClassifiedEntity

_DEFAULT_REF = SourceRef(
    repo="https://github.com/OpenNeuroDatasets", committish="", file="", checksum=""
)

logger = logging.getLogger(__name__)

# BIDS-standard locations to scan for TSV/CSV files
_SCAN_PATTERNS = [
    "*.tsv",
    "*.csv",
    "phenotype/*.tsv",
    "phenotype/*.csv",
    "phenotype/**/*.tsv",
]

# Max rows to sample for type inference
_SAMPLE_ROWS = 50


def _infer_type(values: list[str]) -> str:
    """Infer data type from a sample of column values."""
    non_empty = [v for v in values if v and v.lower() != "n/a"]
    if not non_empty:
        return "string"

    # Check if all values are numeric
    int_count = 0
    float_count = 0
    for v in non_empty:
        try:
            int(v)
            int_count += 1
            continue
        except ValueError:
            pass
        try:
            float(v)
            float_count += 1
        except ValueError:
            pass

    total = len(non_empty)
    if int_count == total:
        return "integer"
    if (int_count + float_count) == total:
        return "float"
    if all(v.lower() in ("true", "false", "yes", "no", "1", "0") for v in non_empty):
        return "boolean"
    return "string"


def _read_json_sidecar(tsv_path: Path) -> dict:
    """Read companion JSON sidecar for a TSV file (same name, .json extension)."""
    json_path = tsv_path.with_suffix(".json")
    if json_path.exists():
        try:
            return json.loads(json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {}


class OpenNeuroAdapter(BaseAdapter):
    """Extract elements from OpenNeuro BIDS datasets via datalad."""

    @property
    def name(self) -> str:
        return "openneuro"

    @property
    def supported_formats(self) -> list[str]:
        return ["bids-dataset"]

    def to_linkml(self, source_path: Path, **options: Any) -> Any:
        return None  # Direct extraction, no LinkML conversion

    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        """Extract elements from TSV/CSV files in a BIDS dataset.

        source_path can be:
        - A local path to a BIDS dataset directory
        - An OpenNeuro dataset ID (e.g., "ds000228") — will be cloned via datalad
        """
        from ..models import EntityType

        dataset_path = source_path

        # If source_path looks like a dataset ID, clone via datalad
        if not dataset_path.exists() and len(str(source_path)) < 20:
            dataset_id = str(source_path)
            dataset_path = self._clone_dataset(dataset_id)

        if not dataset_path.exists():
            logger.warning("Dataset path does not exist: %s", dataset_path)
            return []

        dataset_id = dataset_path.name
        source_name = f"openneuro/{dataset_id}"

        results: list[ClassifiedEntity] = []
        seen_columns: set[tuple[str, str]] = set()  # (filename, column_name)

        # Scan for TSV/CSV files
        tsv_files = []
        for pattern in _SCAN_PATTERNS:
            tsv_files.extend(dataset_path.glob(pattern))

        for tsv_path in sorted(set(tsv_files)):
            rel_path = tsv_path.relative_to(dataset_path)
            sidecar = _read_json_sidecar(tsv_path)

            try:
                with open(tsv_path, newline="", encoding="utf-8") as f:
                    delimiter = "\t" if tsv_path.suffix == ".tsv" else ","
                    reader = csv.DictReader(f, delimiter=delimiter)
                    if not reader.fieldnames:
                        continue

                    # Sample rows for type inference
                    rows = []
                    for i, row in enumerate(reader):
                        if i >= _SAMPLE_ROWS:
                            break
                        rows.append(row)

                    for col_name in reader.fieldnames:
                        key = (str(rel_path), col_name)
                        if key in seen_columns:
                            continue
                        seen_columns.add(key)

                        # Infer type from values
                        values = [row.get(col_name, "") for row in rows]
                        data_type = _infer_type(values)

                        # Get description from JSON sidecar
                        col_meta = sidecar.get(col_name, {})
                        description = ""
                        if isinstance(col_meta, dict):
                            description = col_meta.get(
                                "Description", col_meta.get("description", "")
                            )

                        semantic: dict[str, Any] = {"data_type": data_type}
                        if isinstance(col_meta, dict):
                            if col_meta.get("Units"):
                                semantic["unit"] = col_meta["Units"]
                            levels = col_meta.get("Levels", {})
                            if levels and isinstance(levels, dict):
                                semantic["response_options"] = [
                                    {"value": k, "label": v if isinstance(v, str) else k}
                                    for k, v in levels.items()
                                ]

                        results.append(
                            ClassifiedEntity(
                                entity_type=EntityType.ATTRIBUTE,
                                semantic=semantic,
                                provenance={
                                    "source": source_name,
                                    "class": str(rel_path),
                                    "name": col_name,
                                    "description": description[:500] if description else None,
                                },
                                confidence=0.8,
                                source_ref=_DEFAULT_REF,
                            )
                        )

            except (OSError, csv.Error) as exc:
                logger.warning("Failed to read %s: %s", tsv_path, exc)

        logger.info("Extracted %d elements from %s", len(results), dataset_id)
        return results

    def _clone_dataset(self, dataset_id: str) -> Path:
        """Clone an OpenNeuro dataset via datalad (metadata only)."""
        tmp_dir = Path(tempfile.mkdtemp(prefix=f"openneuro-{dataset_id}-"))
        url = f"https://github.com/OpenNeuroDatasets/{dataset_id}.git"
        logger.info("Cloning %s via datalad to %s", url, tmp_dir)

        try:
            subprocess.run(
                ["datalad", "clone", url, str(tmp_dir / dataset_id)],
                check=True,
                capture_output=True,
                timeout=300,
            )
            dataset_path = tmp_dir / dataset_id

            # Get only metadata files (TSV, JSON)
            for pattern in ["*.tsv", "*.json", "phenotype/*"]:
                try:
                    subprocess.run(
                        ["datalad", "get", "-d", str(dataset_path), pattern],
                        check=False,
                        capture_output=True,
                        timeout=120,
                    )
                except subprocess.TimeoutExpired:
                    pass

            return dataset_path
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            logger.warning("datalad clone failed for %s: %s", dataset_id, exc)
            return tmp_dir / dataset_id
