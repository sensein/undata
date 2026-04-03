"""BIDS schema adapter — delegates to standalone extraction script.

The actual extraction happens in standalone_scripts/bids_extract.py running in an
isolated venv with bidsschematools + linkml-runtime. This adapter class exists
for the registry and for direct file-based extraction when bidsschematools
happens to be available in the current environment.

There is ONE extraction path: standalone script → JSON entities or LinkML YAML
→ main process consumes. No in-process import of bidsschematools is required.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import SourceRef
from .base import BaseAdapter, ClassifiedEntity


class BIDSAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "bids"

    @property
    def supported_formats(self) -> list[str]:
        return []

    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        """Extract entities from BIDS schema.

        Primary path: standalone script in isolated venv (via pipeline).
        Fallback: direct extraction if bidsschematools is in current env.
        """
        try:
            from bidsschematools import schema as bids_schema
        except ImportError:
            return []

        schema = bids_schema.load_schema()
        base_ref = self._build_source_ref(source_path)
        return self._extract_from_schema(schema, base_ref)

    def _extract_from_schema(self, schema: Any, base_ref: SourceRef) -> list[ClassifiedEntity]:
        """Extract entities from a loaded bidsschematools schema object."""
        from ..models import EntityType

        _VOCAB = {
            "enums",
            "datatypes",
            "modalities",
            "suffixes",
            "extensions",
            "formats",
            "common_principles",
        }
        TYPE_MAP = {
            "string": "string",
            "number": "float",
            "integer": "integer",
            "boolean": "boolean",
            "array": "array",
            "object": "object",
        }

        results: list[ClassifiedEntity] = []
        objects = schema.get("objects", {})
        sidecars = schema.get("rules", {}).get("sidecars", {})
        tabular = schema.get("rules", {}).get("tabular_data", {})

        # 1. Vocabulary → enum_value + valueset
        for cat_name in _VOCAB:
            cat = objects.get(cat_name, {})
            for field_name in cat:
                fdef = cat[field_name]
                if not hasattr(fdef, "get"):
                    continue
                if field_name.startswith("_"):
                    evs = fdef.get("enum", [])
                    if evs:
                        members = []
                        for v in evs:
                            if v is None:
                                continue
                            if isinstance(v, dict):
                                parts = v.get("$ref", "").split(".")
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
                else:
                    value = str(fdef.get("value", field_name))
                    display = str(fdef.get("display_name", "") or "")
                    desc = str(fdef.get("description", "") or "")
                    results.append(
                        ClassifiedEntity(
                            entity_type=EntityType.ENUM_VALUE,
                            semantic={
                                "label": value,
                                "value_type": "categorical",
                                "display_name": display,
                            },
                            provenance={
                                "source": "bids",
                                "class": cat_name,
                                "name": field_name,
                                "description": desc or None,
                            },
                            confidence=0.95,
                            source_ref=base_ref,
                        )
                    )

        # 2. Metadata + columns → attribute
        for cat_name in ("metadata", "columns"):
            cat = objects.get(cat_name, {})
            if hasattr(cat, "keys"):
                prop_names = [k for k in cat if not k.startswith("_")]
                results.append(
                    ClassifiedEntity(
                        entity_type=EntityType.CLASS,
                        semantic={"properties": prop_names},
                        provenance={"source": "bids", "class": cat_name, "name": cat_name},
                        confidence=0.9,
                        source_ref=base_ref,
                    )
                )
            for field_name in cat:
                fdef = cat[field_name]
                if not hasattr(fdef, "get") or field_name.startswith("_"):
                    continue
                t = fdef.get("type", "string")
                if isinstance(t, (list, tuple)):
                    t = t[0] if t else "string"
                dt = TYPE_MAP.get(str(t), "string")
                sem: dict[str, Any] = {"data_type": dt}
                unit = fdef.get("unit")
                if unit:
                    sem["unit"] = str(unit)
                pattern = fdef.get("pattern")
                if pattern:
                    sem["pattern"] = str(pattern)
                evs = fdef.get("enum")
                if evs and hasattr(evs, "__iter__"):
                    allowed = [str(v) for v in evs if v is not None]
                    sem["response_options"] = [{"value": v, "label": v} for v in allowed]
                    sem["value_domain"] = "categorical"
                elif dt in ("integer", "float"):
                    sem["value_domain"] = "numeric"
                elif dt == "boolean":
                    sem["value_domain"] = "boolean"
                elif dt == "string":
                    sem["value_domain"] = "text"
                min_val = fdef.get("minimum")
                max_val = fdef.get("maximum")
                if min_val is not None:
                    sem["min_value"] = float(min_val)
                if max_val is not None:
                    sem["max_value"] = float(max_val)
                ref = fdef.get("$ref")
                if ref and isinstance(ref, str):
                    sem["type_ref"] = ref
                desc = str(fdef.get("description", "") or "")
                results.append(
                    ClassifiedEntity(
                        entity_type=EntityType.ATTRIBUTE,
                        semantic=sem,
                        provenance={
                            "source": "bids",
                            "class": cat_name,
                            "name": field_name,
                            "description": desc or None,
                        },
                        confidence=0.85,
                        source_ref=base_ref,
                    )
                )

        # 3. Entities → attribute (filename components)
        for field_name in objects.get("entities", {}):
            fdef = objects["entities"][field_name]
            if not hasattr(fdef, "get"):
                continue
            fmt = str(fdef.get("format", "label"))
            dt = "integer" if fmt == "index" else "string"
            desc = str(fdef.get("description", "") or "")
            results.append(
                ClassifiedEntity(
                    entity_type=EntityType.ATTRIBUTE,
                    semantic={
                        "data_type": dt,
                        "value_domain": "numeric" if dt == "integer" else "text",
                    },
                    provenance={
                        "source": "bids",
                        "class": "entities",
                        "name": field_name,
                        "description": desc or None,
                    },
                    confidence=0.85,
                    source_ref=base_ref,
                )
            )

        # 4. Sidecar rules → class (mixin field groups + concrete modality)
        for modality in sorted(sidecars.keys()):
            groups = sidecars[modality]
            if not hasattr(groups, "keys"):
                continue
            mixin_names = []
            for gname, group in groups.items():
                if not hasattr(group, "get"):
                    continue
                fields = group.get("fields", {})
                if not hasattr(fields, "keys") or not fields:
                    continue
                results.append(
                    ClassifiedEntity(
                        entity_type=EntityType.CLASS,
                        semantic={"properties": list(fields.keys()), "is_mixin": True},
                        provenance={
                            "source": "bids",
                            "class": gname,
                            "name": gname,
                            "description": f"Sidecar field group for {modality}",
                        },
                        confidence=0.9,
                        source_ref=base_ref,
                    )
                )
                mixin_names.append(gname)
            if mixin_names:
                results.append(
                    ClassifiedEntity(
                        entity_type=EntityType.CLASS,
                        semantic={"properties": [], "mixins": mixin_names},
                        provenance={
                            "source": "bids",
                            "class": f"{modality}_sidecar",
                            "name": f"{modality}_sidecar",
                            "description": f"BIDS sidecar for {modality}",
                        },
                        confidence=0.9,
                        source_ref=base_ref,
                    )
                )

        # 5. Tabular data rules → class
        for tname in sorted(tabular.keys()):
            groups = tabular[tname]
            if not hasattr(groups, "keys"):
                continue
            for gname, group in groups.items():
                if not hasattr(group, "get"):
                    continue
                cols = group.get("columns", group.get("fields", {}))
                if not hasattr(cols, "keys") or not cols:
                    continue
                results.append(
                    ClassifiedEntity(
                        entity_type=EntityType.CLASS,
                        semantic={"properties": list(cols.keys()), "is_mixin": True},
                        provenance={
                            "source": "bids",
                            "class": f"{tname}_{gname}",
                            "name": f"{tname}_{gname}",
                            "description": f"Tabular columns for {tname}",
                        },
                        confidence=0.9,
                        source_ref=base_ref,
                    )
                )

        return results

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
        return SourceRef(repo=repo, committish=committish, file="schema", checksum="")
