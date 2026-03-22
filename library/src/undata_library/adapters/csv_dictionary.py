"""CSV/TSV data dictionary adapter."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path
from typing import Any

from ..models import EntityType, SourceRef
from .base import BaseAdapter, ClassifiedEntity


class CSVDictionaryAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "csv"

    @property
    def supported_formats(self) -> list[str]:
        return [".csv", ".tsv"]

    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        repo = options.get("repo")
        committish = options.get("committish")

        # Configurable column names
        name_col = options.get("name_column", "variable_name")
        type_col = options.get("type_column", "field_type")
        desc_col = options.get("description_column", "field_label")
        values_col = options.get("values_column", "select_choices")

        results: list[ClassifiedEntity] = []
        files = (
            [source_path]
            if source_path.is_file()
            else sorted(list(source_path.glob("*.csv")) + list(source_path.glob("*.tsv")))
        )

        for f in files:
            file_ref = SourceRef(
                repo=repo,
                committish=committish,
                file=str(f),
                checksum=hashlib.sha256(f.read_bytes()).hexdigest(),
            )

            delimiter = "\t" if f.suffix == ".tsv" else ","
            try:
                text = f.read_text(encoding="utf-8")
            except OSError:
                continue

            reader = csv.DictReader(text.splitlines(), delimiter=delimiter)
            headers = reader.fieldnames or []

            # Auto-detect column names if configured ones not found
            name_key = _find_col(
                headers, name_col, ["variable_name", "name", "field_name", "variable"]
            )
            type_key = _find_col(headers, type_col, ["field_type", "type", "data_type", "dtype"])
            desc_key = _find_col(headers, desc_col, ["field_label", "description", "label", "desc"])
            values_key = _find_col(
                headers,
                values_col,
                ["select_choices", "allowed_values", "choices", "values", "enum"],
            )

            schema_name = f.stem

            for row in reader:
                var_name = row.get(name_key, "").strip()
                if not var_name:
                    continue

                raw_type = row.get(type_key, "").strip().lower() if type_key else ""
                desc = row.get(desc_key, "").strip() if desc_key else ""
                raw_values = row.get(values_key, "").strip() if values_key else ""

                dt = _infer_type(raw_type, raw_values)
                semantic: dict[str, Any] = {"data_type": dt}

                # Parse allowed values
                if raw_values:
                    choices = _parse_choices(raw_values)
                    if choices:
                        semantic["response_options"] = [{"value": v, "label": v} for v in choices]
                        semantic["value_domain"] = "categorical"
                elif dt in ("integer", "float"):
                    semantic["value_domain"] = "numeric"
                elif dt == "boolean":
                    semantic["value_domain"] = "boolean"
                elif dt == "string":
                    semantic["value_domain"] = "text"

                results.append(
                    ClassifiedEntity(
                        entity_type=EntityType.ATTRIBUTE,
                        semantic=semantic,
                        provenance={
                            "source": "csv",
                            "class": schema_name,
                            "name": var_name,
                            "description": desc or None,
                        },
                        confidence=0.85,
                        source_ref=file_ref,
                    )
                )

        return results


def _find_col(headers: list[str], preferred: str, fallbacks: list[str]) -> str | None:
    """Find column name, trying preferred first then fallbacks (case-insensitive)."""
    lower_map = {h.lower(): h for h in headers}
    if preferred.lower() in lower_map:
        return lower_map[preferred.lower()]
    for fb in fallbacks:
        if fb.lower() in lower_map:
            return lower_map[fb.lower()]
    return None


_TYPE_KEYWORDS = {
    "int": "integer",
    "integer": "integer",
    "numeric": "float",
    "number": "float",
    "float": "float",
    "decimal": "float",
    "double": "float",
    "bool": "boolean",
    "boolean": "boolean",
    "yesno": "boolean",
    "date": "string",
    "datetime": "string",
    "text": "string",
    "string": "string",
    "dropdown": "string",
    "radio": "string",
    "checkbox": "string",
}


def _infer_type(raw_type: str, raw_values: str) -> str:
    """Infer data type from type column or allowed values."""
    if raw_type:
        for keyword, dt in _TYPE_KEYWORDS.items():
            if keyword in raw_type:
                return dt
    # If allowed values present but no type → string (categorical)
    if raw_values:
        return "string"
    return "string"


def _parse_choices(raw: str) -> list[str]:
    """Parse choice strings like '1, Male | 2, Female' or 'a;b;c'."""
    if "|" in raw:
        parts = [p.strip() for p in raw.split("|")]
        choices = []
        for p in parts:
            # Handle 'code, label' format (REDCap style)
            if "," in p:
                label = p.split(",", 1)[1].strip()
                choices.append(label)
            else:
                choices.append(p)
        return choices
    if ";" in raw:
        return [p.strip() for p in raw.split(";") if p.strip()]
    if "," in raw:
        return [p.strip() for p in raw.split(",") if p.strip()]
    return [raw.strip()] if raw.strip() else []
