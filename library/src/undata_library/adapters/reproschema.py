"""ReproSchema adapter — extract elements from reproschema-library activities and items.

ReproSchema uses JSON-LD with a well-defined schema:
- Activities → SchemaRecord (CLASS) entities
- Items → ElementRecord (ATTRIBUTE) entities
- Response options → ValueSet entities

JSON-LD references may be relative paths (e.g., items/foo, ../valueConstraints)
or absolute URLs. This adapter resolves them relative to the containing file.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..models import SourceRef
from .base import BaseAdapter, ClassifiedEntity

_DEFAULT_REF = SourceRef(
    repo="https://github.com/ReproNim/reproschema-library", committish="", file="", checksum=""
)

logger = logging.getLogger(__name__)


def _load_jsonld(path: Path) -> dict | None:
    """Load a JSON-LD file, trying with and without common extensions."""
    for candidate in [path, path.with_suffix(".jsonld"), path.with_suffix("")]:
        if candidate.exists() and candidate.is_file():
            try:
                return json.loads(candidate.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
    return None


def _resolve_ref(ref: str, base_dir: Path) -> dict | None:
    """Resolve a relative path or URL reference to a JSON-LD object.

    If ref is a relative path, resolve it against base_dir and load the file.
    If ref is a URL, return None (not fetched).
    """
    if ref.startswith("http://") or ref.startswith("https://"):
        return None  # URL references not resolved locally
    resolved = (base_dir / ref).resolve()
    return _load_jsonld(resolved)


def _extract_label(obj: Any) -> str:
    """Extract English label from a multilingual dict or string."""
    if isinstance(obj, dict):
        return str(obj.get("en", next(iter(obj.values()), "")))
    return str(obj) if obj else ""


def _parse_response_options(item_data: dict, item_dir: Path) -> tuple[list[dict] | None, dict]:
    """Extract response options from a ReproSchema item.

    Handles both inline dicts and relative path references.
    Returns (options_list, resolved_ro_dict).
    """
    ro = item_data.get("responseOptions", {})

    # Resolve relative path reference
    if isinstance(ro, str):
        resolved = _resolve_ref(ro, item_dir)
        if resolved:
            ro = resolved
        else:
            return None, {}

    if not isinstance(ro, dict):
        return None, {}

    choices = ro.get("choices", [])
    if not choices:
        return None, ro

    options = []
    for choice in choices:
        if isinstance(choice, dict):
            name = choice.get("name", choice.get("schema:name", ""))
            label = _extract_label(name) if name else ""
            options.append(
                {
                    "value": str(choice.get("value", choice.get("schema:value", ""))),
                    "label": label,
                }
            )
        elif isinstance(choice, str):
            options.append({"value": choice, "label": choice})
    return (options if options else None), ro


def _infer_type_from_response(ro: dict) -> str:
    """Infer data type from resolved responseOptions dict."""
    if not isinstance(ro, dict):
        return "string"

    value_type = ro.get("valueType", ro.get("schema:valueType", ""))
    # valueType can be a list like ["xsd:integer"]
    if isinstance(value_type, list):
        value_type = value_type[0] if value_type else ""
    vt_str = str(value_type).lower()

    if "integer" in vt_str or "int" in vt_str:
        return "integer"
    if "float" in vt_str or "double" in vt_str or "decimal" in vt_str:
        return "float"
    if "boolean" in vt_str or "bool" in vt_str:
        return "boolean"
    if ro.get("choices"):
        return "string"  # Categorical

    min_val = ro.get("minValue", ro.get("schema:minValue"))
    max_val = ro.get("maxValue", ro.get("schema:maxValue"))
    if min_val is not None or max_val is not None:
        return "integer"

    return "string"


class ReproSchemaAdapter(BaseAdapter):
    """Extract elements from ReproSchema library activities and items."""

    @property
    def name(self) -> str:
        return "reproschema"

    @property
    def supported_formats(self) -> list[str]:
        return ["reproschema"]

    def to_linkml(self, source_path: Path, **options: Any) -> Any:
        return None  # Direct extraction

    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        """Extract entities from a reproschema-library directory.

        Expected structure:
        activities/
          {activity_name}/
            {activity_name}_schema  (JSON-LD — the activity)
            items/
              {item_name}  (JSON-LD — individual items)
        """
        from ..models import EntityType

        activities_dir = source_path / "activities"
        if not activities_dir.exists():
            logger.warning("No activities/ directory found at %s", source_path)
            return []

        results: list[ClassifiedEntity] = []

        for activity_dir in sorted(activities_dir.iterdir()):
            if not activity_dir.is_dir():
                continue

            activity_name = activity_dir.name

            # Find and load activity schema file
            activity_data = None
            for suffix in ["_schema", "Schema", "_schema.jsonld"]:
                candidate = activity_dir / f"{activity_name}{suffix}"
                activity_data = _load_jsonld(candidate)
                if activity_data:
                    break

            activity_desc = ""
            item_refs: list[str] = []  # variable names from addProperties

            if activity_data:
                desc = activity_data.get("description", activity_data.get("schema:description", ""))
                activity_desc = _extract_label(desc)

                # Get item references from ui.addProperties or order
                ui = activity_data.get("ui", {})
                if isinstance(ui, dict):
                    add_props = ui.get("addProperties", [])
                    for prop in add_props:
                        if isinstance(prop, dict):
                            var_name = prop.get("variableName", "")
                            if var_name:
                                item_refs.append(var_name)
                    if not item_refs:
                        order = ui.get("order", activity_data.get("order", []))
                        item_refs = [str(o).rsplit("/", 1)[-1] for o in order]

            # Create activity as CLASS entity
            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.CLASS,
                    semantic={
                        "properties": item_refs,
                        "description": activity_desc[:500] if activity_desc else None,
                    },
                    provenance={
                        "source": "reproschema",
                        "class": activity_name,
                        "name": activity_name,
                        "description": activity_desc[:500] if activity_desc else None,
                    },
                    confidence=0.9,
                    source_ref=_DEFAULT_REF,
                )
            )

            # Extract items from items/ directory
            items_dir = activity_dir / "items"
            if not items_dir.exists():
                continue

            for item_file in sorted(items_dir.iterdir()):
                if item_file.is_dir() or item_file.name.startswith("."):
                    continue

                item_data = _load_jsonld(item_file)
                if not item_data:
                    continue

                item_name = item_file.stem
                question = _extract_label(
                    item_data.get("question", item_data.get("schema:question", ""))
                )
                description = _extract_label(
                    item_data.get("description", item_data.get("schema:description", ""))
                )

                # Parse response options — resolves relative path references
                response_options, resolved_ro = _parse_response_options(item_data, items_dir)
                data_type = _infer_type_from_response(resolved_ro)

                semantic: dict[str, Any] = {"data_type": data_type}

                if question:
                    semantic["question_text"] = question[:500]

                if response_options:
                    semantic["response_options"] = response_options

                # Min/max from resolved responseOptions
                if resolved_ro.get("minValue") is not None:
                    try:
                        semantic["min_value"] = float(resolved_ro["minValue"])
                    except (ValueError, TypeError):
                        pass
                if resolved_ro.get("maxValue") is not None:
                    try:
                        semantic["max_value"] = float(resolved_ro["maxValue"])
                    except (ValueError, TypeError):
                        pass

                results.append(
                    ClassifiedEntity(
                        entity_type=EntityType.ATTRIBUTE,
                        semantic=semantic,
                        provenance={
                            "source": "reproschema",
                            "class": activity_name,
                            "name": item_name,
                            "description": (description or question)[:500] or None,
                        },
                        confidence=0.85,
                        source_ref=_DEFAULT_REF,
                    )
                )

                # Create ENUM_VALUE entities for each choice + a VALUESET to group them
                if response_options and len(response_options) > 1:
                    value_names = []
                    for opt in response_options:
                        val = opt.get("value", "")
                        label = opt.get("label", val)
                        value_names.append(val)
                        results.append(
                            ClassifiedEntity(
                                entity_type=EntityType.ENUM_VALUE,
                                semantic={
                                    "value_type": "categorical",
                                    "label": str(label)[:200],
                                    "description": f"Response option for {item_name}: {label}"[
                                        :500
                                    ],
                                },
                                provenance={
                                    "source": "reproschema",
                                    "class": activity_name,
                                    "name": f"{item_name}:{val}",
                                    "description": str(label)[:200],
                                },
                                confidence=0.85,
                                source_ref=_DEFAULT_REF,
                            )
                        )

                    # VALUESET grouping all choices for this item
                    results.append(
                        ClassifiedEntity(
                            entity_type=EntityType.VALUESET,
                            semantic={
                                "name": f"{item_name}_options",
                                "members": value_names,
                                "description": f"Response options for {item_name}"[:500],
                            },
                            provenance={
                                "source": "reproschema",
                                "class": activity_name,
                                "name": f"{item_name}_options",
                                "description": f"Response options for {item_name}",
                            },
                            confidence=0.85,
                            source_ref=_DEFAULT_REF,
                        )
                    )

        logger.info(
            "Extracted %d entities from reproschema-library at %s",
            len(results),
            source_path,
        )
        return results
