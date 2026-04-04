"""NDA (National Data Archive) data dictionary adapter.

Fetches data dictionaries from the NDA API
(https://nda.nih.gov/api/datadictionary/v2/) and extracts elements,
valuesets, and schema classes from each data structure.

Usage:
    adapter.extract(Path("."), structures=["image03", "genomics_subject02"])

The source_path argument is ignored (data comes from the API). Pass
structure short names via the ``structures`` keyword option.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import httpx

from ..models import EntityType, SourceRef
from .base import BaseAdapter, ClassifiedEntity

logger = logging.getLogger(__name__)

NDA_API_BASE = "https://nda.nih.gov/api/datadictionary/v2"

# NDA type string → internal data type
_NDA_TYPE_MAP: dict[str, str] = {
    "String": "string",
    "Integer": "integer",
    "Float": "float",
    "Date": "string",
    "Thumbnail": "string",
    "File": "string",
    "GUID": "string",
    "Conditional": "string",
}


def _map_nda_type(nda_type: str) -> str:
    """Map an NDA type name to our DataType string."""
    return _NDA_TYPE_MAP.get(nda_type, "string")


def _parse_value_range(value_range: str | None) -> tuple[float | None, float | None]:
    """Parse NDA valueRange string into (min, max).

    NDA valueRange can look like:
      "0 :: 100"       → min=0, max=100
      "0::100"         → min=0, max=100
      "-1 :: 1"        → min=-1, max=1
      "0 ::"           → min=0, max=None
      ":: 100"         → min=None, max=100
    """
    if not value_range or not value_range.strip():
        return None, None

    value_range = value_range.strip()
    if "::" not in value_range:
        return None, None

    parts = value_range.split("::")
    if len(parts) != 2:
        return None, None

    min_val: float | None = None
    max_val: float | None = None

    left = parts[0].strip()
    right = parts[1].strip()

    if left:
        try:
            min_val = float(left)
        except ValueError:
            pass

    if right:
        try:
            max_val = float(right)
        except ValueError:
            pass

    return min_val, max_val


def _parse_notes(notes: str | None) -> list[dict[str, str]]:
    """Parse NDA notes field into response options.

    NDA notes can contain semicolon-delimited coded values like:
      "1=Male; 2=Female; -1=Unknown"
      "0 = No ; 1 = Yes"
    """
    if not notes or not notes.strip():
        return []

    options: list[dict[str, str]] = []
    # Split on semicolons
    entries = notes.split(";")
    for entry in entries:
        entry = entry.strip()
        if not entry:
            continue
        # Match patterns like "1=Male" or "1 = Male"
        match = re.match(r"^\s*([^=]+?)\s*=\s*(.+?)\s*$", entry)
        if match:
            value = match.group(1).strip()
            label = match.group(2).strip()
            options.append({"value": value, "label": label})

    return options


def _fetch_structure(client: httpx.Client, short_name: str) -> dict[str, Any] | None:
    """Fetch a single data structure from NDA API."""
    url = f"{NDA_API_BASE}/datastructure/{short_name}"
    try:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()
    except httpx.HTTPStatusError as exc:
        logger.warning("NDA API error for %s: %s", short_name, exc)
        return None
    except httpx.RequestError as exc:
        logger.warning("NDA API request failed for %s: %s", short_name, exc)
        return None


def _fetch_structure_list(client: httpx.Client) -> list[str]:
    """Fetch the list of all available NDA data structure short names."""
    url = f"{NDA_API_BASE}/datastructure"
    try:
        resp = client.get(url)
        resp.raise_for_status()
        data = resp.json()
        # API returns a list of objects each with a "shortName" field
        return [item["shortName"] for item in data if "shortName" in item]
    except (httpx.HTTPStatusError, httpx.RequestError) as exc:
        logger.warning("NDA API failed to list structures: %s", exc)
        return []


def _dedup_elements(entities: list[ClassifiedEntity]) -> list[ClassifiedEntity]:
    """Deduplicate ATTRIBUTE entities that share the same (name, data_type).

    When the same element (e.g. "subjectkey", "interview_date") appears in
    multiple NDA structures with identical semantics, keep a single entity and
    merge provenance:
    - ``alias_hints`` accumulates all ``nda:<structure>`` short names
    - ``provenance`` comes from the first occurrence

    Non-ATTRIBUTE entities (ENUM_VALUE, VALUESET, CLASS) pass through unchanged.
    """
    deduped: list[ClassifiedEntity] = []
    # (name, data_type) → index in deduped list
    seen: dict[tuple[str, str], int] = {}

    for entity in entities:
        if entity.entity_type != EntityType.ATTRIBUTE:
            deduped.append(entity)
            continue

        name = entity.provenance.get("name", "")
        data_type = entity.semantic.get("data_type", "")
        key = (name, data_type)

        structure_hint = f"nda:{entity.provenance.get('class', '')}"

        if key in seen:
            # Merge: add structure to alias_hints of the existing entity
            existing = deduped[seen[key]]
            alias_hints = existing.semantic.setdefault("alias_hints", [])
            if structure_hint not in alias_hints:
                alias_hints.append(structure_hint)
        else:
            # First occurrence — record it
            seen[key] = len(deduped)
            entity.semantic.setdefault("alias_hints", [structure_hint])
            deduped.append(entity)

    return deduped


class NDAAdapter(BaseAdapter):
    """Adapter for the NIMH Data Archive (NDA) data dictionaries."""

    @property
    def name(self) -> str:
        return "nda"

    @property
    def supported_formats(self) -> list[str]:
        return []

    def to_linkml(self, source_path: Path, **options: Any) -> Any:
        """Build LinkML SchemaDefinition from NDA data dictionaries.

        Maps: structures → classes, fields → slots (deduplicated across structures),
        coded values → enums, NDA aliases → slot aliases.
        """
        from . import linkml_builder as lb

        structures_list: list[str] | None = options.get("structures")
        timeout = options.get("timeout", 30.0)

        schema = lb.build_schema("nda", "https://nda.nih.gov/schema", title="NDA Data Dictionary")

        with httpx.Client(timeout=timeout, headers={"Accept": "application/json"}) as client:
            if structures_list is None:
                structures_list = _fetch_structure_list(client)
                if not structures_list:
                    logger.warning("No NDA structures found or API unavailable")
                    return None

            for short_name in structures_list:
                structure = _fetch_structure(client, short_name)
                if structure is None:
                    continue
                self._add_structure_to_schema(schema, structure, short_name)

        return schema

    def _add_structure_to_schema(
        self, schema: Any, structure: dict[str, Any], short_name: str
    ) -> None:
        """Add a single NDA structure to the SchemaDefinition."""
        from . import linkml_builder as lb

        data_elements = structure.get("dataElements", [])
        slot_names: list[str] = []

        for elem in data_elements:
            name = elem.get("name", "")
            if not name:
                continue
            slot_names.append(name)

            description = elem.get("description", "") or ""
            nda_type = elem.get("type", "String") or "String"
            value_range = elem.get("valueRange")
            notes = elem.get("notes")
            aliases_raw = elem.get("aliases")

            dt = _map_nda_type(nda_type)
            linkml_range = {"integer": "integer", "float": "float", "boolean": "boolean"}.get(
                dt, "string"
            )

            # Parse value range
            min_val, max_val = _parse_value_range(value_range)

            # Parse aliases
            alias_list: list[str] = []
            if aliases_raw:
                if isinstance(aliases_raw, list):
                    alias_list = aliases_raw
                elif isinstance(aliases_raw, str) and aliases_raw not in ("[]", "None", ""):
                    try:
                        import json as _json

                        alias_list = _json.loads(aliases_raw)
                    except (ValueError, TypeError):
                        alias_list = [aliases_raw]

            # Parse notes for enum values
            response_options = _parse_notes(notes)
            if response_options:
                enum_name = f"{name}_values"
                vals = [opt["value"] for opt in response_options]
                lb.add_enum(schema, enum_name, vals, description=f"Coded values for {name}")
                linkml_range = enum_name

            lb.add_slot(
                schema,
                name,
                range=linkml_range,
                description=description[:500] if description else None,
                minimum_value=min_val,
                maximum_value=max_val,
                aliases=alias_list if alias_list else None,
            )

        # Structure → class
        title = structure.get("title", short_name)
        lb.add_class(schema, short_name, slots=slot_names, description=title)

    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        """Extract entities via LinkML SchemaDefinition + SchemaView."""
        from .extractor import extract_from_schema_definition

        schema_def = self.to_linkml(source_path, **options)
        if schema_def is None:
            return []

        source_ref = SourceRef(
            repo="https://nda.nih.gov",
            committish=None,
            file="datadictionary",
            checksum="",
        )
        return extract_from_schema_definition(schema_def, source_name="nda", source_ref=source_ref)
