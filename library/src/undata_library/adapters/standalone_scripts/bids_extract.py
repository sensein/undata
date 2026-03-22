#!/usr/bin/env python3
"""Standalone BIDS extraction script — runs in isolated venv with only bidsschematools.

Converts BIDS schema to a flat entity list (ClassifiedEntity-compatible dicts).
Uses the same category-aware classification as the main BIDSAdapter.

Entity classification:
- Vocabulary categories (enums, datatypes, modalities, suffixes, extensions):
  entries → enum_value, underscore entries → valueset + enum_value members
- Attribute categories (metadata, columns): entries → attribute, category → class
- Entity category (entities): filename components → attribute (tagged)
- Sidecar rules: field groups → class (mixin), modalities → class (concrete)
"""

import json

_VOCABULARY_CATEGORIES = {
    "enums",
    "datatypes",
    "modalities",
    "suffixes",
    "extensions",
    "formats",
    "common_principles",
}
_ATTRIBUTE_CATEGORIES = {"metadata", "columns"}
_ENTITY_CATEGORIES = {"entities"}

TYPE_MAP = {
    "string": "string",
    "number": "float",
    "integer": "integer",
    "boolean": "boolean",
    "array": "array",
    "object": "object",
}


def _bids_type(field_def):
    t = field_def.get("type", "string") if hasattr(field_def, "get") else "string"
    if isinstance(t, (list, tuple)):
        t = t[0] if t else "string"
    return TYPE_MAP.get(str(t), "string")


def _extract_valueset(cat_name, field_name, field_def, results):
    enum_vals = field_def.get("enum") if hasattr(field_def, "get") else None
    if not enum_vals or not hasattr(enum_vals, "__iter__"):
        return
    members = []
    for v in enum_vals:
        if v is None:
            continue
        if isinstance(v, dict):
            ref = v.get("$ref", "")
            parts = ref.split(".")
            members.append(parts[-2] if len(parts) >= 3 else str(v))
        else:
            members.append(str(v))
    results.append(
        {
            "entity_type": "valueset",
            "semantic": {"name": field_name.lstrip("_"), "members": sorted(members)},
            "provenance": {"source": "bids", "class": cat_name, "name": field_name},
            "confidence": 0.9,
        }
    )
    for val in members:
        results.append(
            {
                "entity_type": "enum_value",
                "semantic": {"label": val, "value_type": "categorical"},
                "provenance": {"source": "bids", "class": cat_name, "name": val},
                "confidence": 0.95,
            }
        )


def main():
    from bidsschematools import schema as bids_schema

    schema = bids_schema.load_schema()
    results = []
    objects = schema.get("objects", {})
    sidecars = schema.get("rules", {}).get("sidecars", {})
    tabular = schema.get("rules", {}).get("tabular_data", {})

    # 1. Vocabulary categories → enum_value
    for cat_name in _VOCABULARY_CATEGORIES:
        category = objects.get(cat_name, {})
        for field_name in category:
            field_def = category[field_name]
            if not hasattr(field_def, "get"):
                continue
            if field_name.startswith("_"):
                _extract_valueset(cat_name, field_name, field_def, results)
                continue
            value = str(field_def.get("value", field_name))
            display_name = str(field_def.get("display_name", "") or "")
            desc = str(field_def.get("description", "") or "")
            results.append(
                {
                    "entity_type": "enum_value",
                    "semantic": {
                        "label": value,
                        "value_type": "categorical",
                        "display_name": display_name,
                    },
                    "provenance": {
                        "source": "bids",
                        "class": cat_name,
                        "name": field_name,
                        "description": desc or None,
                    },
                    "confidence": 0.95,
                }
            )

    # 2. Attribute categories → attribute + class
    for cat_name in _ATTRIBUTE_CATEGORIES:
        category = objects.get(cat_name, {})
        if not category:
            continue
        if hasattr(category, "keys"):
            prop_names = [k for k in category if not k.startswith("_")]
            results.append(
                {
                    "entity_type": "class",
                    "semantic": {"properties": prop_names},
                    "provenance": {"source": "bids", "class": cat_name, "name": cat_name},
                    "confidence": 0.9,
                }
            )
        for field_name in category:
            field_def = category[field_name]
            if not hasattr(field_def, "get"):
                continue
            if field_name.startswith("_"):
                _extract_valueset(cat_name, field_name, field_def, results)
                continue
            dt = _bids_type(field_def)
            desc = str(field_def.get("description", "") or "")
            semantic = {"data_type": dt}
            unit = field_def.get("unit")
            if unit:
                semantic["unit"] = str(unit)
            pattern = field_def.get("pattern")
            if pattern:
                semantic["pattern"] = str(pattern)
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
            min_val = field_def.get("minimum")
            max_val = field_def.get("maximum")
            if min_val is not None:
                semantic["min_value"] = float(min_val)
            if max_val is not None:
                semantic["max_value"] = float(max_val)
            results.append(
                {
                    "entity_type": "attribute",
                    "semantic": semantic,
                    "provenance": {
                        "source": "bids",
                        "class": cat_name,
                        "name": field_name,
                        "description": desc or None,
                    },
                    "confidence": 0.85,
                }
            )

    # 3. Entity category → attribute (filename components)
    entities_cat = objects.get("entities", {})
    for field_name in entities_cat:
        field_def = entities_cat[field_name]
        if not hasattr(field_def, "get"):
            continue
        desc = str(field_def.get("description", "") or "")
        fmt = str(field_def.get("format", "label"))
        dt = "integer" if fmt == "index" else "string"
        results.append(
            {
                "entity_type": "attribute",
                "semantic": {
                    "data_type": dt,
                    "value_domain": "numeric" if dt == "integer" else "text",
                },
                "provenance": {
                    "source": "bids",
                    "class": "entities",
                    "name": field_name,
                    "description": desc or None,
                },
                "confidence": 0.85,
            }
        )

    # 4. Sidecar rules → classes (field groups as mixins, modalities as concrete)
    for modality in sorted(sidecars.keys()):
        groups = sidecars[modality]
        if not hasattr(groups, "keys"):
            continue
        mixin_names = []
        for group_name, group in groups.items():
            if not hasattr(group, "get"):
                continue
            fields = group.get("fields", {})
            if not hasattr(fields, "keys") or not fields:
                continue
            field_names = list(fields.keys())
            results.append(
                {
                    "entity_type": "class",
                    "semantic": {"properties": field_names, "is_mixin": True},
                    "provenance": {
                        "source": "bids",
                        "class": group_name,
                        "name": group_name,
                        "description": f"Sidecar field group for {modality}",
                    },
                    "confidence": 0.9,
                }
            )
            mixin_names.append(group_name)
        if mixin_names:
            results.append(
                {
                    "entity_type": "class",
                    "semantic": {"properties": [], "mixins": mixin_names},
                    "provenance": {
                        "source": "bids",
                        "class": f"{modality}_sidecar",
                        "name": f"{modality}_sidecar",
                        "description": f"BIDS sidecar for {modality}",
                    },
                    "confidence": 0.9,
                }
            )

    # 5. Tabular data rules → classes
    for table_name in sorted(tabular.keys()):
        groups = tabular[table_name]
        if not hasattr(groups, "keys"):
            continue
        for group_name, group in groups.items():
            if not hasattr(group, "get"):
                continue
            cols = group.get("columns", group.get("fields", {}))
            if not hasattr(cols, "keys") or not cols:
                continue
            col_names = list(cols.keys())
            results.append(
                {
                    "entity_type": "class",
                    "semantic": {"properties": col_names, "is_mixin": True},
                    "provenance": {
                        "source": "bids",
                        "class": f"{table_name}_{group_name}",
                        "name": f"{table_name}_{group_name}",
                        "description": f"Tabular columns for {table_name}",
                    },
                    "confidence": 0.9,
                }
            )

    print(json.dumps(results))


if __name__ == "__main__":
    main()
