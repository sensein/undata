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

    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        """Extract entities from NDA data dictionaries.

        Options:
            structures: list[str] — short names of structures to fetch
                (e.g., ["image03", "genomics_subject02"]).
                If omitted, fetches all available structures (can be slow).
            timeout: float — HTTP timeout in seconds (default 30).
        """
        structures: list[str] | None = options.get("structures")
        timeout = options.get("timeout", 30.0)

        results: list[ClassifiedEntity] = []

        with httpx.Client(
            timeout=timeout,
            headers={"Accept": "application/json"},
        ) as client:
            if structures is None:
                structures = _fetch_structure_list(client)
                if not structures:
                    logger.warning("No NDA structures found or API unavailable")
                    return []

            for short_name in structures:
                structure = _fetch_structure(client, short_name)
                if structure is None:
                    continue
                results.extend(self._extract_structure(structure, short_name))

        # Deduplicate elements across structures when extracting multiple
        if len(structures) > 1:
            results = _dedup_elements(results)

        return results

    def _extract_structure(
        self, structure: dict[str, Any], short_name: str
    ) -> list[ClassifiedEntity]:
        """Extract entities from a single NDA data structure response."""
        results: list[ClassifiedEntity] = []

        title = structure.get("title", short_name)
        data_elements = structure.get("dataElements", [])

        source_ref = SourceRef(
            repo="https://nda.nih.gov",
            committish=None,
            file=f"datastructure/{short_name}",
            checksum="",
        )

        # Collect element names for the schema class
        element_names: list[str] = []

        for elem in data_elements:
            name = elem.get("name", "")
            if not name:
                continue
            element_names.append(name)

            description = elem.get("description", "") or ""
            nda_type = elem.get("type", "String") or "String"
            value_range = elem.get("valueRange")
            notes = elem.get("notes")
            required_val = elem.get("required")
            aliases = elem.get("aliases")
            size = elem.get("size")

            dt = _map_nda_type(nda_type)

            # Build semantic dict
            semantic: dict[str, Any] = {"data_type": dt}

            # Parse value range for min/max
            min_val, max_val = _parse_value_range(value_range)
            if min_val is not None:
                semantic["min_value"] = min_val
            if max_val is not None:
                semantic["max_value"] = max_val

            # Parse notes for coded values (response options)
            response_options = _parse_notes(notes)
            if response_options:
                semantic["response_options"] = response_options
                semantic["value_domain"] = "categorical"
            elif dt in ("integer", "float"):
                semantic["value_domain"] = "numeric"
            elif dt == "boolean":
                semantic["value_domain"] = "boolean"
            elif dt == "string":
                semantic["value_domain"] = "text"

            if size is not None:
                try:
                    semantic["max_length"] = int(size)
                except (ValueError, TypeError):
                    pass

            # Build provenance dict
            provenance: dict[str, Any] = {
                "source": "nda",
                "class": short_name,
                "name": name,
                "description": description or None,
            }
            if required_val is not None:
                provenance["required"] = required_val in ("Required", True)
            if aliases:
                provenance["aliases"] = aliases
                # Also add to semantic for alignment module alias detection
                alias_list = aliases if isinstance(aliases, list) else []
                if isinstance(aliases, str) and aliases not in ("[]", "None", ""):
                    try:
                        import json as _json

                        alias_list = _json.loads(aliases)
                    except (ValueError, TypeError):
                        alias_list = [aliases]
                if alias_list:
                    existing_hints = semantic.get("alias_hints", [])
                    existing_hints.extend([f"nda_alias:{a}" for a in alias_list])
                    semantic["alias_hints"] = existing_hints

            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.ATTRIBUTE,
                    semantic=semantic,
                    provenance=provenance,
                    confidence=0.85,
                    source_ref=source_ref,
                )
            )

            # If element has coded values, also emit enum_values + valueset
            if response_options:
                # Emit individual enum values
                for opt in response_options:
                    results.append(
                        ClassifiedEntity(
                            entity_type=EntityType.ENUM_VALUE,
                            semantic={
                                "label": opt.get("label", opt["value"]),
                                "value_type": "categorical",
                            },
                            provenance={
                                "source": "nda",
                                "class": short_name,
                                "name": opt["value"],
                                "description": opt.get("label"),
                            },
                            confidence=0.90,
                            source_ref=source_ref,
                        )
                    )

                # Emit valueset grouping the coded values
                members = [opt["value"] for opt in response_options]
                results.append(
                    ClassifiedEntity(
                        entity_type=EntityType.VALUESET,
                        semantic={
                            "name": f"{short_name}_{name}_values",
                            "members": members,
                        },
                        provenance={
                            "source": "nda",
                            "class": short_name,
                            "name": f"{name}_values",
                        },
                        confidence=0.90,
                        source_ref=source_ref,
                    )
                )

        # Emit schema class for the data structure
        if element_names:
            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.CLASS,
                    semantic={"properties": element_names},
                    provenance={
                        "source": "nda",
                        "class": short_name,
                        "name": short_name,
                        "description": title,
                    },
                    confidence=0.90,
                    source_ref=source_ref,
                )
            )

        return results
