#!/usr/bin/env python3
"""Standalone DANDI extraction script — runs in isolated venv with only dandischema.

Outputs JSON list of ClassifiedEntity-compatible dicts to stdout.
"""

import enum
import inspect
import json
import typing


_PROPERTY_VALUE_VARIANTS = {
    "age": [
        ("age", "postnatal age (ISO 8601 duration, valueReference=BirthReference)", {}),
        (
            "gestational_age",
            "gestational age (ISO 8601 duration, valueReference=GestationalReference)",
            {},
        ),
    ],
}


def main():
    import dandischema.models as dm

    results = []

    for cls_name, cls in inspect.getmembers(dm, inspect.isclass):
        if not hasattr(cls, "model_fields"):
            continue

        results.append(
            {
                "entity_type": "class",
                "semantic": {"properties": list(cls.model_fields.keys())},
                "provenance": {"source": "dandi", "class": cls_name, "name": cls_name},
                "confidence": 0.9,
            }
        )

        for field_name, field_info in cls.model_fields.items():
            ann = field_info.annotation
            desc = field_info.description or ""

            if field_name in _PROPERTY_VALUE_VARIANTS and "PropertyValue" in str(ann or ""):
                for variant_name, variant_desc, extra in _PROPERTY_VALUE_VARIANTS[field_name]:
                    results.append(
                        {
                            "entity_type": "attribute",
                            "semantic": {"data_type": "string", **extra},
                            "provenance": {
                                "source": "dandi",
                                "class": cls_name,
                                "name": variant_name,
                                "description": f"{desc} ({variant_desc})",
                            },
                            "confidence": 0.9,
                        }
                    )
                continue

            dt = _pydantic_type(field_info)
            semantic = {"data_type": dt}

            if ann is not None:
                enum_cls = _extract_enum_class(ann)
                if enum_cls:
                    allowed = [str(v.value) for v in enum_cls]
                    if allowed:
                        semantic["response_options"] = [{"value": v, "label": v} for v in allowed]
                        results.append(
                            {
                                "entity_type": "valueset",
                                "semantic": {"name": enum_cls.__name__, "members": sorted(allowed)},
                                "provenance": {
                                    "source": "dandi",
                                    "class": cls_name,
                                    "name": enum_cls.__name__,
                                },
                                "confidence": 0.9,
                            }
                        )

            if hasattr(field_info, "metadata"):
                for m in field_info.metadata:
                    for attr, key in [
                        ("ge", "min_value"),
                        ("gt", "min_value"),
                        ("le", "max_value"),
                        ("lt", "max_value"),
                    ]:
                        if hasattr(m, attr) and getattr(m, attr) is not None:
                            semantic[key] = float(getattr(m, attr))

            results.append(
                {
                    "entity_type": "attribute",
                    "semantic": semantic,
                    "provenance": {
                        "source": "dandi",
                        "class": cls_name,
                        "name": field_name,
                        "description": desc,
                    },
                    "confidence": 0.85,
                }
            )

    print(json.dumps(results))


def _extract_enum_class(annotation):
    origin = getattr(annotation, "__origin__", None)
    if origin is typing.Union:
        for arg in annotation.__args__:
            if isinstance(arg, type) and issubclass(arg, enum.Enum):
                return arg
    if isinstance(annotation, type) and issubclass(annotation, enum.Enum):
        return annotation
    return None


def _pydantic_type(field_info):
    ann = str(field_info.annotation) if field_info.annotation else "string"
    if "int" in ann.lower():
        return "integer"
    if "float" in ann.lower():
        return "float"
    if "bool" in ann.lower():
        return "boolean"
    if "list" in ann.lower():
        return "array"
    return "string"


if __name__ == "__main__":
    main()
