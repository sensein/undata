#!/usr/bin/env python3
"""Standalone BIDS extraction script — runs in isolated venv with only bidsschematools.

Outputs JSON list of ClassifiedEntity-compatible dicts to stdout.

Entity classification:
- Vocabulary categories (enums, datatypes, modalities, suffixes, extensions, formats):
  entries → enum_value, underscore entries → valueset + enum_value members
- Attribute categories (metadata, columns): entries → attribute, category → class
- Entity category (entities): filename components → attribute (tagged)
"""

import json


# Categories whose entries are vocabulary terms (enum_value), not data elements
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
    """Extract underscore-prefixed entries as valueset + enum_value members."""
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
    for cat_name in objects:
        category = objects[cat_name]
        if not hasattr(category, "__iter__"):
            continue

        if cat_name in _VOCABULARY_CATEGORIES:
            # Vocabulary terms → enum_value
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

        elif cat_name in _ATTRIBUTE_CATEGORIES:
            # Emit category as class with property list
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

        elif cat_name in _ENTITY_CATEGORIES:
            # Filename entities → attribute (tagged)
            for field_name in category:
                field_def = category[field_name]
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
                            "class": cat_name,
                            "name": field_name,
                            "description": desc or None,
                        },
                        "confidence": 0.85,
                    }
                )
        else:
            # Unknown category — extract as attributes
            for field_name in category:
                field_def = category[field_name]
                if not hasattr(field_def, "get"):
                    continue
                dt = _bids_type(field_def)
                desc = str(field_def.get("description", "") or "")
                semantic = {"data_type": dt}
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

    print(json.dumps(results))


if __name__ == "__main__":
    main()
