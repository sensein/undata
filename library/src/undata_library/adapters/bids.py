"""BIDS schema adapter — uses bidsschematools."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import EntityType, SourceRef
from .base import BaseAdapter, ClassifiedEntity
from .classifier import classify_entity

_TYPE_MAP = {
    "string": "string",
    "number": "float",
    "integer": "integer",
    "boolean": "boolean",
    "array": "array",
    "object": "object",
}


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

        # Determine source_ref from bidsschematools install location
        base_ref = self._build_source_ref(source_path)

        objects = schema.get("objects", {})
        for cat_name in objects:
            category = objects[cat_name]
            if not hasattr(category, "__iter__"):
                continue

            # Classify the category itself
            cat_type_info = {"properties": dict(category)} if hasattr(category, "keys") else {}
            if cat_type_info.get("properties"):
                cat_etype, cat_conf = classify_entity(cat_name, cat_type_info)
                if cat_etype == EntityType.CLASS:
                    results.append(
                        ClassifiedEntity(
                            entity_type=EntityType.CLASS,
                            semantic={"properties": []},  # populated later by ingest
                            provenance={"source": "bids", "class": cat_name, "name": cat_name},
                            confidence=cat_conf,
                            source_ref=base_ref,
                            source_context={"category": cat_name},
                        )
                    )

            for field_name in category:
                if field_name.startswith("_"):
                    # Underscore entries are valuesets
                    field_def = category[field_name]
                    if not hasattr(field_def, "get"):
                        continue
                    enum_vals = field_def.get("enum") if hasattr(field_def, "get") else None
                    if enum_vals and hasattr(enum_vals, "__iter__"):
                        members = [str(v) for v in enum_vals if v is not None]
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
                        # Also emit individual enum values
                        for val in members:
                            results.append(
                                ClassifiedEntity(
                                    entity_type=EntityType.ENUM_VALUE,
                                    semantic={"label": val, "value_type": "categorical"},
                                    provenance={"source": "bids", "raw_value": val},
                                    confidence=0.95,
                                    source_ref=base_ref,
                                )
                            )
                    continue

                field_def = category[field_name]
                if not hasattr(field_def, "get"):
                    continue

                dt = _bids_type(field_def)
                desc = str(field_def.get("description", "") or "")

                # Build type_info for classifier
                type_info: dict[str, Any] = {"type": dt}
                enum_vals = field_def.get("enum") if hasattr(field_def, "get") else None
                if enum_vals and hasattr(enum_vals, "__iter__"):
                    type_info["enum"] = list(enum_vals)

                etype, conf = classify_entity(field_name, type_info, parent=cat_name)

                # Build semantic dict
                semantic: dict[str, Any] = {"data_type": dt}
                if enum_vals:
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
                if hasattr(field_def, "get"):
                    min_val = field_def.get("minimum")
                    max_val = field_def.get("maximum")
                    if min_val is not None:
                        semantic["min_value"] = float(min_val)
                    if max_val is not None:
                        semantic["max_value"] = float(max_val)

                results.append(
                    ClassifiedEntity(
                        entity_type=etype,
                        semantic=semantic,
                        provenance={
                            "source": "bids",
                            "class": cat_name,
                            "name": field_name,
                            "description": desc or None,
                        },
                        confidence=conf,
                        source_ref=base_ref,
                        source_context={"category": cat_name},
                    )
                )

        return results

    def _build_source_ref(self, source_path: Path) -> SourceRef:
        """Build source_ref for BIDS.

        Uses --repo and --committish options if provided, otherwise derives from
        bidsschematools package metadata.
        """
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
