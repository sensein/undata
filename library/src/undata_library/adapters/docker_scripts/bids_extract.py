#!/usr/bin/env python3
"""Standalone BIDS extraction script — runs in isolated venv with only bidsschematools.

Outputs JSON list of ClassifiedEntity-compatible dicts to stdout.
"""

import json


def main():
    from bidsschematools import schema as bids_schema

    schema = bids_schema.load_schema()
    results = []

    TYPE_MAP = {
        "string": "string",
        "number": "float",
        "integer": "integer",
        "boolean": "boolean",
        "array": "array",
        "object": "object",
    }

    objects = schema.get("objects", {})
    for cat_name in objects:
        category = objects[cat_name]
        if not hasattr(category, "__iter__"):
            continue

        # Emit class
        if hasattr(category, "keys"):
            results.append(
                {
                    "entity_type": "class",
                    "semantic": {"properties": []},
                    "provenance": {"source": "bids", "class": cat_name, "name": cat_name},
                    "confidence": 0.9,
                }
            )

        for field_name in category:
            field_def = category[field_name]
            if not hasattr(field_def, "get"):
                continue

            if field_name.startswith("_"):
                # Valueset
                enum_vals = field_def.get("enum") if hasattr(field_def, "get") else None
                if enum_vals and hasattr(enum_vals, "__iter__"):
                    members = [str(v) for v in enum_vals if v is not None]
                    results.append(
                        {
                            "entity_type": "valueset",
                            "semantic": {
                                "name": field_name.lstrip("_"),
                                "members": sorted(members),
                            },
                            "provenance": {"source": "bids", "class": cat_name, "name": field_name},
                            "confidence": 0.9,
                        }
                    )
                    for val in members:
                        results.append(
                            {
                                "entity_type": "enum_value",
                                "semantic": {"label": val, "value_type": "categorical"},
                                "provenance": {"source": "bids", "raw_value": val},
                                "confidence": 0.95,
                            }
                        )
                continue

            # Regular field → attribute
            t = field_def.get("type", "string") if hasattr(field_def, "get") else "string"
            if isinstance(t, (list, tuple)):
                t = t[0] if t else "string"
            dt = TYPE_MAP.get(str(t), "string")
            desc = str(field_def.get("description", "") or "")

            semantic = {"data_type": dt}
            enum_vals = field_def.get("enum") if hasattr(field_def, "get") else None
            if enum_vals and hasattr(enum_vals, "__iter__"):
                allowed = [str(v) for v in enum_vals if v is not None]
                semantic["constraints"] = {"allowed_values": allowed}
                semantic["response_options"] = [{"value": v, "label": v} for v in allowed]
                semantic["value_domain"] = "categorical"
            elif dt in ("integer", "float"):
                semantic["value_domain"] = "numeric"
            elif dt == "boolean":
                semantic["value_domain"] = "boolean"
            elif dt == "string":
                semantic["value_domain"] = "text"

            if hasattr(field_def, "get"):
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

    print(json.dumps(results))


if __name__ == "__main__":
    main()
