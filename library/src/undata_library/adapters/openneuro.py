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

from ..models import EntityType, SourceRef
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
        return None  # Direct extraction, no LinkML conversion

    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        """Extract elements from TSV/CSV + JSON files in a BIDS dataset.

        source_path can be:
        - A local path to a BIDS dataset directory
        - An OpenNeuro dataset ID (e.g., "ds000228") — will be cloned via datalad
        """
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

        # 1. Extract from TSV/CSV files
        results.extend(self._extract_from_tsvs(dataset_path, source_name))

        # 2. Extract from JSON metadata files (protocol params, column descriptors)
        results.extend(self._extract_from_jsons(dataset_path, source_name))

        logger.info("Extracted %d entities from %s", len(results), dataset_id)
        return results

    def _extract_from_tsvs(self, dataset_path: Path, source_name: str) -> list[ClassifiedEntity]:
        """Extract ATTRIBUTE + ENUM_VALUE + VALUESET from TSV/CSV files."""
        results: list[ClassifiedEntity] = []
        seen_columns: set[tuple[str, str]] = set()

        # Also read top-level JSON sidecars for column metadata
        participants_json = self._read_json_sidecar(dataset_path / "participants.tsv")

        tsv_files = []
        for pattern in _TSV_PATTERNS:
            tsv_files.extend(dataset_path.glob(pattern))

        for tsv_path in sorted(set(tsv_files)):
            rel_path = str(tsv_path.relative_to(dataset_path))
            sidecar = self._read_json_sidecar(tsv_path)
            # Merge with participants.json if this is participants.tsv
            if tsv_path.name == "participants.tsv" and participants_json:
                # participants.json may have nested structure
                flat_meta = {}
                for k, v in participants_json.items():
                    if _is_column_descriptor(v):
                        flat_meta[k] = v
                    elif isinstance(v, dict):
                        # Nested group like "Theory of Mind (ToM) Measures Metadata"
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

                    # Sample rows for type inference + unique value collection
                    rows = []
                    for i, row in enumerate(reader):
                        if i >= _SAMPLE_ROWS:
                            break
                        rows.append(row)

                    for col_name in reader.fieldnames:
                        key = (rel_path, col_name)
                        if key in seen_columns:
                            continue
                        seen_columns.add(key)

                        values = [row.get(col_name, "") for row in rows]
                        data_type = _infer_type(values)

                        # Get description from JSON sidecar
                        col_meta = sidecar.get(col_name, {})
                        description = ""
                        unit = None
                        levels = None
                        if isinstance(col_meta, dict):
                            description = col_meta.get(
                                "Description", col_meta.get("description", "")
                            )
                            unit = col_meta.get("Units", col_meta.get("units"))
                            levels = col_meta.get("Levels", {})

                        semantic: dict[str, Any] = {"data_type": data_type}
                        if unit:
                            semantic["unit"] = unit

                        # Build response_options from Levels or unique values
                        if isinstance(levels, dict) and levels:
                            semantic["response_options"] = [
                                {"value": k, "label": v if isinstance(v, str) else k}
                                for k, v in levels.items()
                            ]
                        elif data_type == "string":
                            unique_vals = sorted(set(v for v in values if v and v.lower() != "n/a"))
                            if 1 < len(unique_vals) <= _MAX_ENUM_VALUES:
                                semantic["response_options"] = [
                                    {"value": v, "label": v} for v in unique_vals
                                ]

                        # ATTRIBUTE entity
                        results.append(
                            ClassifiedEntity(
                                entity_type=EntityType.ATTRIBUTE,
                                semantic=semantic,
                                provenance={
                                    "source": source_name,
                                    "class": rel_path,
                                    "name": col_name,
                                    "description": str(description)[:500] if description else None,
                                },
                                confidence=0.8,
                                source_ref=_DEFAULT_REF,
                            )
                        )

                        # ENUM_VALUE + VALUESET for categorical columns
                        ro = semantic.get("response_options")
                        if ro and len(ro) > 1:
                            value_names = []
                            for opt in ro:
                                val = opt["value"]
                                label = opt["label"]
                                value_names.append(val)
                                results.append(
                                    ClassifiedEntity(
                                        entity_type=EntityType.ENUM_VALUE,
                                        semantic={
                                            "value_type": "categorical",
                                            "label": str(label)[:200],
                                            "description": f"{col_name} option: {label}"[:500],
                                        },
                                        provenance={
                                            "source": source_name,
                                            "class": rel_path,
                                            "name": f"{col_name}:{val}",
                                            "description": str(label)[:200],
                                        },
                                        confidence=0.8,
                                        source_ref=_DEFAULT_REF,
                                    )
                                )
                            results.append(
                                ClassifiedEntity(
                                    entity_type=EntityType.VALUESET,
                                    semantic={
                                        "name": f"{col_name}_values",
                                        "members": value_names,
                                        "description": f"Values for {col_name} in {rel_path}",
                                    },
                                    provenance={
                                        "source": source_name,
                                        "class": rel_path,
                                        "name": f"{col_name}_values",
                                        "description": f"Values for {col_name}",
                                    },
                                    confidence=0.8,
                                    source_ref=_DEFAULT_REF,
                                )
                            )

            except (OSError, csv.Error) as exc:
                logger.warning("Failed to read %s: %s", tsv_path, exc)

        return results

    def _extract_from_jsons(self, dataset_path: Path, source_name: str) -> list[ClassifiedEntity]:
        """Extract ATTRIBUTE elements from top-level JSON files (protocol metadata).

        Keys like EchoTime, RepetitionTime, MagneticFieldStrength become elements.
        Nested column descriptors (with Description/Levels) are handled by TSV extraction.
        """
        results: list[ClassifiedEntity] = []
        seen_keys: set[tuple[str, str]] = set()

        json_files = []
        for pattern in _JSON_PATTERNS:
            json_files.extend(dataset_path.glob(pattern))

        for json_path in sorted(set(json_files)):
            if json_path.name == "dataset_description.json":
                continue  # Metadata about the dataset, not data elements
            if json_path.name == "participants.json":
                continue  # Handled in TSV extraction

            try:
                data = json.loads(json_path.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    continue
            except (json.JSONDecodeError, OSError):
                continue

            rel_path = str(json_path.relative_to(dataset_path))

            for key, value in data.items():
                if key in _SKIP_JSON_KEYS:
                    continue
                if key.startswith("dcmmeta_"):
                    continue  # Internal dcm2niix metadata
                if _is_column_descriptor(value):
                    continue  # Column descriptor, handled with TSV

                dup_key = (rel_path, key)
                if dup_key in seen_keys:
                    continue
                seen_keys.add(dup_key)

                data_type = _infer_type_from_value(value)
                semantic: dict[str, Any] = {"data_type": data_type}

                # Extract unit from key name heuristics
                if isinstance(value, (int, float)):
                    if "Time" in key or "time" in key:
                        semantic["unit"] = "s"
                    elif "Strength" in key:
                        semantic["unit"] = "T"

                results.append(
                    ClassifiedEntity(
                        entity_type=EntityType.ATTRIBUTE,
                        semantic=semantic,
                        provenance={
                            "source": source_name,
                            "class": rel_path,
                            "name": key,
                            "description": f"BIDS metadata field: {key} = {str(value)[:100]}",
                        },
                        confidence=0.7,
                        source_ref=_DEFAULT_REF,
                    )
                )

        return results

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
