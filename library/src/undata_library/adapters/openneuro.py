"""OpenNeuro adapter — extract elements from BIDS datasets via datalad.

Scans each dataset for:
- TSV/CSV files (participants.tsv, phenotype/*.tsv, derivatives/**/*.csv)
- JSON sidecars (participants.json, task-*.json, sub-*/.../*.json)
- dataset_description.json metadata

Extracts ATTRIBUTE elements from TSV columns and JSON keys,
ENUM_VALUE + VALUESET from categorical columns and Levels fields.
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

# Locations to scan for TSV/CSV files (recursive)
_TSV_PATTERNS = [
    "*.tsv",
    "*.csv",
    "phenotype/*.tsv",
    "phenotype/*.csv",
    "phenotype/**/*.tsv",
    "derivatives/**/*.tsv",
    "derivatives/**/*.csv",
]

# JSON files to scan for protocol/metadata elements
_JSON_PATTERNS = [
    "*.json",
    "phenotype/*.json",
]

# Max rows to sample for type inference
_SAMPLE_ROWS = 50

# Max unique values before treating as non-categorical
_MAX_ENUM_VALUES = 30

# JSON keys to skip (not data elements)
_SKIP_JSON_KEYS = {
    "Name",
    "BIDSVersion",
    "License",
    "Authors",
    "Acknowledgements",
    "HowToAcknowledge",
    "Funding",
    "ReferencesAndLinks",
    "DatasetDOI",
    "GeneratedBy",
    "SourceDatasets",
}

# Keys whose values are nested dicts describing columns (like participants.json)
_COLUMN_DESC_INDICATORS = {"Description", "Levels", "TermURL", "Units"}


def _infer_type(values: list[str]) -> str:
    """Infer data type from a sample of column values."""
    non_empty = [v for v in values if v and v.lower() != "n/a"]
    if not non_empty:
        return "string"

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


def _infer_type_from_value(value: Any) -> str:
    """Infer data type from a single JSON value."""
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "float"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "string"


def _is_column_descriptor(value: Any) -> bool:
    """Check if a JSON value looks like a BIDS column descriptor (has Description/Levels)."""
    if not isinstance(value, dict):
        return False
    return bool(set(value.keys()) & _COLUMN_DESC_INDICATORS)


class OpenNeuroAdapter(BaseAdapter):
    """Extract elements from OpenNeuro BIDS datasets via datalad."""

    @property
    def name(self) -> str:
        return "openneuro"

    @property
    def supported_formats(self) -> list[str]:
        return ["bids-dataset"]

    def to_linkml(self, source_path: Path, **options: Any) -> Any:
        """Build LinkML SchemaDefinition from OpenNeuro BIDS dataset.

        Maps: TSV file types → classes, columns → slots (shared across files),
        categorical values/Levels → enums, JSON sidecar fields → slots.
        """
        from . import linkml_builder as lb

        dataset_path = source_path

        if not dataset_path.exists() and len(str(source_path)) < 20:
            dataset_id = str(source_path)
            dataset_path = self._clone_dataset(dataset_id)

        if not dataset_path.exists():
            logger.warning("Dataset path does not exist: %s", dataset_path)
            return None

        dataset_id = dataset_path.name
        schema = lb.build_schema(
            f"openneuro_{dataset_id}",
            f"https://openneuro.org/datasets/{dataset_id}",
            title=f"OpenNeuro {dataset_id}",
        )

        # Read participants.json for column metadata
        participants_json = self._read_json_sidecar(dataset_path / "participants.tsv")

        # 1. Scan TSV/CSV files → slots and classes
        tsv_files: list[Path] = []
        for pattern in _TSV_PATTERNS:
            tsv_files.extend(dataset_path.glob(pattern))

        for tsv_path in sorted(set(tsv_files)):
            rel_path = str(tsv_path.relative_to(dataset_path))
            sidecar = self._read_json_sidecar(tsv_path)

            if tsv_path.name == "participants.tsv" and participants_json:
                flat_meta = {}
                for k, v in participants_json.items():
                    if _is_column_descriptor(v):
                        flat_meta[k] = v
                    elif isinstance(v, dict):
                        for sub_k, sub_v in v.items():
                            if _is_column_descriptor(sub_v):
                                flat_meta[sub_k] = sub_v
                sidecar = {**flat_meta, **sidecar}

            try:
                with open(tsv_path, newline="", encoding="utf-8") as f:
                    delimiter = "\t" if tsv_path.suffix == ".tsv" else ","
                    reader = csv.DictReader(f, delimiter=delimiter)
                    if not reader.fieldnames:
                        continue

                    rows = []
                    for i, row in enumerate(reader):
                        if i >= _SAMPLE_ROWS:
                            break
                        rows.append(row)

                    slot_names: list[str] = []
                    for col_name in reader.fieldnames:
                        values = [row.get(col_name, "") for row in rows]
                        data_type = _infer_type(values)
                        linkml_range = {
                            "integer": "integer",
                            "float": "float",
                            "boolean": "boolean",
                        }.get(data_type, "string")

                        col_meta = sidecar.get(col_name, {})
                        description = ""
                        unit = None
                        min_val = None
                        max_val = None
                        levels = None
                        if isinstance(col_meta, dict):
                            description = col_meta.get(
                                "Description", col_meta.get("description", "")
                            )
                            unit = col_meta.get("Units", col_meta.get("units"))
                            levels = col_meta.get("Levels", {})
                            min_val_raw = col_meta.get(
                                "MinValue",
                                col_meta.get("Minimum", col_meta.get("minimum")),
                            )
                            max_val_raw = col_meta.get(
                                "MaxValue",
                                col_meta.get("Maximum", col_meta.get("maximum")),
                            )
                            if min_val_raw is not None:
                                try:
                                    min_val = float(min_val_raw)
                                except (ValueError, TypeError):
                                    pass
                            if max_val_raw is not None:
                                try:
                                    max_val = float(max_val_raw)
                                except (ValueError, TypeError):
                                    pass

                        # Build enum from Levels or unique values
                        enum_name = None
                        if isinstance(levels, dict) and levels:
                            enum_name = f"{col_name}_values"
                            lb.add_enum(schema, enum_name, sorted(levels.keys()))
                            linkml_range = enum_name
                        elif data_type == "string":
                            unique_vals = sorted(set(v for v in values if v and v.lower() != "n/a"))
                            if 1 < len(unique_vals) <= _MAX_ENUM_VALUES:
                                enum_name = f"{col_name}_values"
                                lb.add_enum(schema, enum_name, unique_vals)
                                linkml_range = enum_name

                        lb.add_slot(
                            schema,
                            col_name,
                            range=linkml_range,
                            description=str(description)[:500] if description else None,
                            unit=unit,
                            minimum_value=min_val,
                            maximum_value=max_val,
                        )
                        slot_names.append(col_name)

                    # TSV file → class
                    class_name = rel_path.replace("/", "_").replace(".", "_")
                    lb.add_class(schema, class_name, slots=slot_names)

            except (OSError, csv.Error) as exc:
                logger.warning("Failed to read %s: %s", tsv_path, exc)

        # 2. Scan JSON files → slots for protocol params
        json_files: list[Path] = []
        for pattern in _JSON_PATTERNS:
            json_files.extend(dataset_path.glob(pattern))

        for json_path in sorted(set(json_files)):
            if json_path.name in ("dataset_description.json", "participants.json"):
                continue
            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue
            except (json.JSONDecodeError, OSError):
                continue

            for key, value in data.items():
                if key in _SKIP_JSON_KEYS or key.startswith("dcmmeta_"):
                    continue
                if _is_column_descriptor(value):
                    continue

                data_type = _infer_type_from_value(value)
                linkml_range = {
                    "integer": "integer",
                    "float": "float",
                    "boolean": "boolean",
                }.get(data_type, "string")

                unit = None
                if isinstance(value, (int, float)):
                    if "Time" in key or "time" in key:
                        unit = "s"
                    elif "Strength" in key:
                        unit = "T"

                lb.add_slot(schema, key, range=linkml_range, unit=unit)

        logger.info("Built LinkML schema from OpenNeuro dataset %s", dataset_id)
        return schema

    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        """Extract entities via LinkML SchemaDefinition + SchemaView."""
        from .extractor import extract_from_schema_definition

        schema_def = self.to_linkml(source_path, **options)
        if schema_def is None:
            return []

        dataset_id = source_path.name if source_path.exists() else str(source_path)
        source_name = f"openneuro/{dataset_id}"

        return extract_from_schema_definition(
            schema_def, source_name=source_name, source_ref=_DEFAULT_REF
        )

    def _read_json_sidecar(self, tsv_path: Path) -> dict:
        """Read companion JSON sidecar for a TSV file (same name, .json extension)."""
        json_path = tsv_path.with_suffix(".json")
        if json_path.exists():
            try:
                return json.loads(json_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
        return {}

    def _clone_dataset(self, dataset_id: str) -> Path:
        """Clone an OpenNeuro dataset and fetch metadata files.

        Strategy: git clone (fast, gets annex branch refs) → datalad get (fetches
        actual annexed file content for TSV/JSON metadata).

        OpenNeuro datasets use git-annex — plain git clone only gets pointer files.
        Must use datalad get to retrieve the actual content.
        """
        tmp_dir = Path(tempfile.mkdtemp(prefix=f"openneuro-{dataset_id}-"))
        url = f"https://github.com/OpenNeuroDatasets/{dataset_id}.git"
        dataset_path = tmp_dir / dataset_id
        logger.info("Cloning %s to %s", url, dataset_path)

        # Step 1: git clone (includes annex branch refs)
        try:
            subprocess.run(
                ["git", "clone", url, str(dataset_path)],
                check=True,
                capture_output=True,
                timeout=300,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
            logger.warning("git clone failed for %s: %s", dataset_id, exc)
            return dataset_path

        # Step 2: init git-annex so datalad can work with the repo
        subprocess.run(
            ["git", "-C", str(dataset_path), "annex", "init"],
            check=False,
            capture_output=True,
            timeout=30,
        )

        # Step 3: datalad get for metadata files only (TSV, JSON, phenotype)
        for pattern in [
            "*.tsv",
            "*.json",
            "phenotype/*.tsv",
            "phenotype/*.json",
            "phenotype/**/*.tsv",
        ]:
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
