"""ReproSchema adapter — extract elements from reproschema-library activities and items.

ReproSchema uses JSON-LD with a well-defined schema:
- Activities → SchemaRecord (CLASS) entities
- Items → ElementRecord (ATTRIBUTE) entities
- Response options → ValueSet entities
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


def _parse_response_options(item_data: dict) -> list[dict] | None:
    """Extract response options from a ReproSchema item."""
    ro = item_data.get("responseOptions", {})
    if not ro:
        return None

    choices = ro.get("choices", [])
    if not choices:
        return None

    options = []
    for choice in choices:
        if isinstance(choice, dict):
            options.append(
                {
                    "value": str(choice.get("value", choice.get("schema:value", ""))),
                    "label": str(choice.get("name", choice.get("schema:name", ""))),
                }
            )
        elif isinstance(choice, str):
            options.append({"value": choice, "label": choice})
    return options if options else None


def _infer_type_from_response(item_data: dict) -> str:
    """Infer data type from ReproSchema item responseOptions."""
    ro = item_data.get("responseOptions", {})
    if not ro:
        return "string"

    value_type = ro.get("valueType", ro.get("schema:valueType", ""))
    if "integer" in str(value_type).lower() or "int" in str(value_type).lower():
        return "integer"
    if "float" in str(value_type).lower() or "double" in str(value_type).lower():
        return "float"
    if "boolean" in str(value_type).lower() or "bool" in str(value_type).lower():
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

            # Find activity schema file
            schema_files = list(activity_dir.glob(f"{activity_name}_schema*")) + list(
                activity_dir.glob(f"{activity_name}Schema*")
            )
            activity_desc = ""
            item_order = []

            for sf in schema_files:
                try:
                    activity_data = json.loads(sf.read_text(encoding="utf-8"))
                    activity_desc = activity_data.get(
                        "description",
                        activity_data.get("schema:description", ""),
                    )
                    if isinstance(activity_desc, dict):
                        activity_desc = activity_desc.get("en", str(activity_desc))
                    order = activity_data.get("order", activity_data.get("ui", {}).get("order", []))
                    item_order = [str(o).rsplit("/", 1)[-1] for o in order]
                except (json.JSONDecodeError, OSError):
                    pass

            # Create activity as CLASS entity
            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.CLASS,
                    semantic={
                        "properties": item_order,
                        "description": str(activity_desc)[:500] if activity_desc else None,
                    },
                    provenance={
                        "source": "reproschema",
                        "class": activity_name,
                        "name": activity_name,
                        "description": str(activity_desc)[:500] if activity_desc else None,
                    },
                    confidence=0.9,
                    source_ref=_DEFAULT_REF,
                )
            )

            # Extract items
            items_dir = activity_dir / "items"
            if not items_dir.exists():
                continue

            for item_file in sorted(items_dir.iterdir()):
                if item_file.is_dir() or item_file.name.startswith("."):
                    continue

                try:
                    item_data = json.loads(item_file.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue

                item_name = item_file.stem
                question = item_data.get("question", item_data.get("schema:question", ""))
                if isinstance(question, dict):
                    question = question.get("en", str(question))

                description = item_data.get("description", item_data.get("schema:description", ""))
                if isinstance(description, dict):
                    description = description.get("en", str(description))

                data_type = _infer_type_from_response(item_data)
                semantic: dict[str, Any] = {"data_type": data_type}

                if question:
                    semantic["question_text"] = str(question)[:500]

                response_options = _parse_response_options(item_data)
                if response_options:
                    semantic["response_options"] = response_options

                # Min/max from responseOptions
                ro = item_data.get("responseOptions", {})
                if ro.get("minValue") is not None:
                    try:
                        semantic["min_value"] = float(ro["minValue"])
                    except (ValueError, TypeError):
                        pass
                if ro.get("maxValue") is not None:
                    try:
                        semantic["max_value"] = float(ro["maxValue"])
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
                            "description": str(description or question)[:500] or None,
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
