"""BIDS schema adapter — uses bidsschematools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import EntityType, SourceRef
from .base import BaseAdapter, ClassifiedEntity

_TYPE_MAP = {
    "string": "string",
    "number": "float",
    "integer": "integer",
    "boolean": "boolean",
    "array": "array",
    "object": "object",
}

# Categories whose entries are vocabulary terms (ENUM_VALUE), not data elements
_VOCABULARY_CATEGORIES = frozenset(
    {
        "enums",
        "datatypes",
        "modalities",
        "suffixes",
        "extensions",
        "formats",
        "common_principles",
    }
)

# Categories whose entries are structural data elements (ATTRIBUTE)
_ATTRIBUTE_CATEGORIES = frozenset(
    {
        "metadata",
        "columns",
    }
)

# Categories whose entries are filename structural components
_ENTITY_CATEGORIES = frozenset(
    {
        "entities",
    }
)


class BIDSAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "bids"

    @property
    def supported_formats(self) -> list[str]:
        return []  # Uses bidsschematools API, not file parsing

    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        try:
            from bidsschematools import schema as bids_schema
        except ImportError as exc:
            raise ImportError(f"bidsschematools required for BIDS extraction: {exc}") from exc

        schema = bids_schema.load_schema()
        results: list[ClassifiedEntity] = []
        base_ref = self._build_source_ref(source_path)

        objects = schema.get("objects", {})
        for cat_name in objects:
            category = objects[cat_name]
            if not hasattr(category, "__iter__"):
                continue

            if cat_name in _VOCABULARY_CATEGORIES:
                self._extract_vocabulary(cat_name, category, results, base_ref)
            elif cat_name in _ATTRIBUTE_CATEGORIES:
                self._extract_attributes(cat_name, category, results, base_ref)
            elif cat_name in _ENTITY_CATEGORIES:
                self._extract_entities(cat_name, category, results, base_ref)
            else:
                # Unknown category — extract as attributes by default
                self._extract_attributes(cat_name, category, results, base_ref)

        return results

    def _extract_vocabulary(
        self,
        cat_name: str,
        category: Any,
        results: list[ClassifiedEntity],
        base_ref: SourceRef,
    ) -> None:
        """Extract vocabulary terms as ENUM_VALUE entities.

        Vocabulary categories contain named terms with value, display_name,
        and description fields. These are categorical constants, not data elements.
        """
        for field_name in category:
            field_def = category[field_name]
            if not hasattr(field_def, "get"):
                continue

            if field_name.startswith("_"):
                # Underscore entries are valuesets
                self._extract_valueset(cat_name, field_name, field_def, results, base_ref)
                continue

            # Regular entries are enum values
            value = str(field_def.get("value", field_name))
            display_name = str(field_def.get("display_name", "") or "")
            desc = str(field_def.get("description", "") or "")

            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.ENUM_VALUE,
                    semantic={
                        "label": value,
                        "value_type": "categorical",
                        "display_name": display_name,
                    },
                    provenance={
                        "source": "bids",
                        "class": cat_name,
                        "name": field_name,
                        "description": desc or None,
                    },
                    confidence=0.95,
                    source_ref=base_ref,
                    source_context={"category": cat_name, "value": value},
                )
            )

    def _extract_valueset(
        self,
        cat_name: str,
        field_name: str,
        field_def: Any,
        results: list[ClassifiedEntity],
        base_ref: SourceRef,
    ) -> None:
        """Extract underscore-prefixed entries as VALUESET + their ENUM_VALUE members."""
        enum_vals = field_def.get("enum") if hasattr(field_def, "get") else None
        if not enum_vals or not hasattr(enum_vals, "__iter__"):
            return

        members = []
        for v in enum_vals:
            if v is None:
                continue
            # Handle potential $ref entries
            if isinstance(v, dict):
                ref = v.get("$ref", "")
                # Try to resolve: objects.enums.CapTrak.value → CapTrak
                parts = ref.split(".")
                members.append(parts[-2] if len(parts) >= 3 else str(v))
            else:
                members.append(str(v))

        results.append(
            ClassifiedEntity(
                entity_type=EntityType.VALUESET,
                semantic={
                    "name": field_name.lstrip("_"),
                    "members": sorted(members),
                },
                provenance={
                    "source": "bids",
                    "class": cat_name,
                    "name": field_name,
                },
                confidence=0.9,
                source_ref=base_ref,
            )
        )
        # Emit individual enum values
        for val in members:
            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.ENUM_VALUE,
                    semantic={"label": val, "value_type": "categorical"},
                    provenance={"source": "bids", "class": cat_name, "name": val},
                    confidence=0.95,
                    source_ref=base_ref,
                )
            )

    def _extract_attributes(
        self,
        cat_name: str,
        category: Any,
        results: list[ClassifiedEntity],
        base_ref: SourceRef,
    ) -> None:
        """Extract data element attributes with full semantic metadata."""
        # Emit the category as a CLASS (schema shape)
        if hasattr(category, "keys"):
            prop_names = [k for k in category if not k.startswith("_")]
            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.CLASS,
                    semantic={"properties": prop_names},
                    provenance={"source": "bids", "class": cat_name, "name": cat_name},
                    confidence=0.9,
                    source_ref=base_ref,
                    source_context={"category": cat_name},
                )
            )

        for field_name in category:
            if field_name.startswith("_"):
                # Underscore entries are valuesets even in attribute categories
                field_def = category[field_name]
                if hasattr(field_def, "get"):
                    self._extract_valueset(cat_name, field_name, field_def, results, base_ref)
                continue

            field_def = category[field_name]
            if not hasattr(field_def, "get"):
                continue

            dt = _bids_type(field_def)
            desc = str(field_def.get("description", "") or "")

            # Build semantic dict with full metadata
            semantic: dict[str, Any] = {"data_type": dt}

            # Read unit (critical for cross-source mapping)
            unit = field_def.get("unit")
            if unit:
                semantic["unit"] = str(unit)

            # Read pattern
            pattern = field_def.get("pattern")
            if pattern:
                semantic["pattern"] = str(pattern)

            # Enum values → response_options
            enum_vals = field_def.get("enum") if hasattr(field_def, "get") else None
            if enum_vals and hasattr(enum_vals, "__iter__"):
                allowed = [str(v) for v in enum_vals if v is not None]
                semantic["response_options"] = [{"value": v, "label": v} for v in allowed]
                semantic["value_domain"] = "categorical"
            elif dt in ("integer", "float"):
                semantic["value_domain"] = "numeric"
            elif dt == "boolean":
                semantic["value_domain"] = "boolean"
            elif dt == "string":
                semantic["value_domain"] = "text"

            # Min/max
            min_val = field_def.get("minimum")
            max_val = field_def.get("maximum")
            if min_val is not None:
                semantic["min_value"] = float(min_val)
            if max_val is not None:
                semantic["max_value"] = float(max_val)

            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.ATTRIBUTE,
                    semantic=semantic,
                    provenance={
                        "source": "bids",
                        "class": cat_name,
                        "name": field_name,
                        "description": desc or None,
                    },
                    confidence=0.9,
                    source_ref=base_ref,
                    source_context={"category": cat_name},
                )
            )

    def _extract_entities(
        self,
        cat_name: str,
        category: Any,
        results: list[ClassifiedEntity],
        base_ref: SourceRef,
    ) -> None:
        """Extract BIDS filename entities as tagged attributes."""
        for field_name in category:
            field_def = category[field_name]
            if not hasattr(field_def, "get"):
                continue

            # Entities have name (filename key), format, display_name
            entity_name = str(field_def.get("name", field_name))
            display_name = str(field_def.get("display_name", "") or "")
            desc = str(field_def.get("description", "") or "")
            fmt = str(field_def.get("format", "label"))

            dt = "integer" if fmt == "index" else "string"

            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.ATTRIBUTE,
                    semantic={
                        "data_type": dt,
                        "value_domain": "numeric" if dt == "integer" else "text",
                    },
                    provenance={
                        "source": "bids",
                        "class": cat_name,
                        "name": field_name,
                        "description": desc or None,
                    },
                    confidence=0.85,
                    source_ref=base_ref,
                    source_context={
                        "category": cat_name,
                        "entity_name": entity_name,
                        "format": fmt,
                        "display_name": display_name,
                        "is_filename_entity": True,
                    },
                )
            )

    def _build_source_ref(self, source_path: Path) -> SourceRef:
        repo = "https://github.com/bids-standard/bids-specification"
        committish = None
        try:
            import bidsschematools

            version = getattr(bidsschematools, "__version__", None)
            if version:
                committish = f"v{version}"
        except Exception:
            pass
        return SourceRef(
            repo=repo,
            committish=committish,
            file="schema/objects",
            checksum="",
        )


def _bids_type(field_def: object) -> str:
    t = field_def.get("type", "string") if hasattr(field_def, "get") else "string"
    if isinstance(t, (list, tuple)):
        t = t[0] if t else "string"
    return _TYPE_MAP.get(str(t), "string")
