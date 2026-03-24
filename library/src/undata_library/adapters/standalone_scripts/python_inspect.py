#!/usr/bin/env python3
"""Standalone script injected into Docker containers to introspect Python schema packages.

Outputs JSON list of ClassifiedEntity-compatible dicts to stdout.
Usage: python python_inspect.py <package_name>
"""

import importlib
import inspect
import json
import sys


def main():
    if len(sys.argv) < 2:
        print("Usage: python python_inspect.py <package_name>", file=sys.stderr)
        sys.exit(1)

    package_name = sys.argv[1]

    try:
        pkg = importlib.import_module(package_name)
    except ImportError as e:
        print(json.dumps({"error": f"Cannot import {package_name}: {e}"}))
        sys.exit(1)

    results = []
    seen = set()

    for module_name, module in _iter_modules(pkg):
        for cls_name, cls in inspect.getmembers(module, inspect.isclass):
            if cls_name in seen:
                continue
            seen.add(cls_name)

            # Check for Pydantic models
            if hasattr(cls, "model_fields"):
                results.append(
                    {
                        "entity_type": "class",
                        "semantic": {"properties": list(cls.model_fields.keys())},
                        "provenance": {
                            "source": package_name,
                            "class": cls_name,
                            "name": cls_name,
                            "description": cls.__doc__ or "",
                        },
                        "confidence": 0.9,
                        "source_context": {"module": module_name, "type": "pydantic"},
                    }
                )
                for field_name, field_info in cls.model_fields.items():
                    dt = _infer_type(field_info)
                    results.append(
                        {
                            "entity_type": "attribute",
                            "semantic": {"data_type": dt},
                            "provenance": {
                                "source": package_name,
                                "class": cls_name,
                                "name": field_name,
                                "description": getattr(field_info, "description", "") or "",
                            },
                            "confidence": 0.85,
                            "source_context": {"module": module_name},
                        }
                    )

            # Check for dataclasses
            elif hasattr(cls, "__dataclass_fields__"):
                fields = cls.__dataclass_fields__
                results.append(
                    {
                        "entity_type": "class",
                        "semantic": {"properties": list(fields.keys())},
                        "provenance": {
                            "source": package_name,
                            "class": cls_name,
                            "name": cls_name,
                            "description": cls.__doc__ or "",
                        },
                        "confidence": 0.85,
                        "source_context": {"module": module_name, "type": "dataclass"},
                    }
                )
                for field_name, field in fields.items():
                    dt = _type_str(field.type)
                    results.append(
                        {
                            "entity_type": "attribute",
                            "semantic": {"data_type": dt},
                            "provenance": {
                                "source": package_name,
                                "class": cls_name,
                                "name": field_name,
                                "description": "",
                            },
                            "confidence": 0.8,
                            "source_context": {"module": module_name},
                        }
                    )

    print(json.dumps(results, indent=2))


def _iter_modules(pkg):
    """Yield (module_name, module) for package and submodules."""
    yield pkg.__name__, pkg
    if hasattr(pkg, "__path__"):
        import pkgutil

        for importer, modname, ispkg in pkgutil.walk_packages(
            pkg.__path__, prefix=pkg.__name__ + "."
        ):
            try:
                mod = importlib.import_module(modname)
                yield modname, mod
            except Exception:
                continue


def _infer_type(field_info):
    ann = str(getattr(field_info, "annotation", "")) or ""
    ann_lower = ann.lower()
    if "int" in ann_lower:
        return "integer"
    if "float" in ann_lower:
        return "float"
    if "bool" in ann_lower:
        return "boolean"
    if "list" in ann_lower:
        return "array"
    return "string"


def _type_str(t):
    s = str(t).lower()
    if "int" in s:
        return "integer"
    if "float" in s:
        return "float"
    if "bool" in s:
        return "boolean"
    if "list" in s:
        return "array"
    return "string"


if __name__ == "__main__":
    main()
