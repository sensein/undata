"""Rule-based entity classification with structural signal detection."""

from __future__ import annotations

from typing import Any

from ..models import EntityType


def classify_entity(
    name: str,
    type_info: dict[str, Any],
    parent: str | None = None,
    siblings: list[str] | None = None,
    llm_model: str | None = None,
    llm_threshold: float = 0.7,
) -> tuple[EntityType, float]:
    """Classify a schema entity using structural signals.

    Returns (EntityType, confidence) where confidence is 0.0–1.0.

    Structural signals:
    - Has 'properties' or 'slots' → class (sh:NodeShape)
    - Leaf type with type info → attribute (rdf:Property)
    - 'enum' or 'oneOf' with literal values → enum_value (ValueConcept)
    - Named collection of enum values → valueset (ValueSetRecord)
    - Type reference to another class → attribute with type_ref
    """
    # Check for valueset: named collection of enum values
    if _is_valueset(name, type_info):
        return EntityType.VALUESET, _valueset_confidence(type_info)

    # Check for enum value: literal enum member
    if _is_enum_value(type_info):
        return EntityType.ENUM_VALUE, _enum_confidence(type_info)

    # Check for class: has properties/slots defining a shape
    if _is_class(type_info):
        return EntityType.CLASS, _class_confidence(type_info)

    # Default: attribute (rdf:Property)
    etype, conf = EntityType.ATTRIBUTE, _attribute_confidence(type_info)

    # LLM fallback when confidence is low
    if conf < llm_threshold and llm_model:
        try:
            from .llm_classifier import LLMClassifier

            llm = LLMClassifier(llm_model)
            llm_type, llm_conf, _reasoning = llm.classify(
                name, type_info, parent=parent, siblings=siblings
            )
            return llm_type, llm_conf
        except Exception:
            pass  # Fall through to rule-based result

    return etype, conf


def _is_valueset(name: str, type_info: dict) -> bool:
    """Detect if entity is a named collection of enum values."""
    # Explicit enum with named members and no other properties
    if type_info.get("type") == "enum" and type_info.get("members"):
        return True

    # JSON Schema: enum array at top level of a named definition
    if "enum" in type_info and isinstance(type_info["enum"], list) and len(type_info["enum"]) > 1:
        # If it has no 'properties', it's a standalone enum = valueset
        if "properties" not in type_info:
            return True

    # JSON Schema: oneOf/anyOf with all const/literal values
    for key in ("oneOf", "anyOf"):
        items = type_info.get(key, [])
        if items and all(isinstance(v, dict) and ("const" in v or "enum" in v) for v in items):
            return True

    # LinkML: enum_range or permissible_values
    if type_info.get("permissible_values") or type_info.get("enum_range"):
        return True

    return False


def _is_enum_value(type_info: dict) -> bool:
    """Detect if entity is a single enum/literal value."""
    if type_info.get("const") is not None:
        return True
    if type_info.get("is_enum_member"):
        return True
    return False


def _is_class(type_info: dict) -> bool:
    """Detect if entity is a class (has properties/slots)."""
    if type_info.get("properties") and isinstance(type_info["properties"], dict):
        return True
    if type_info.get("slots") and isinstance(type_info["slots"], list):
        return True
    if type_info.get("type") == "object" and type_info.get("properties"):
        return True
    # LinkML class marker
    if type_info.get("is_a") or type_info.get("mixins"):
        return True
    return False


def _valueset_confidence(type_info: dict) -> float:
    """Confidence for valueset classification."""
    if type_info.get("permissible_values"):
        return 0.95
    if "enum" in type_info and len(type_info.get("enum", [])) > 2:
        return 0.9
    return 0.8


def _enum_confidence(type_info: dict) -> float:
    """Confidence for enum value classification."""
    if type_info.get("const") is not None:
        return 0.95
    return 0.8


def _class_confidence(type_info: dict) -> float:
    """Confidence for class classification."""
    props = type_info.get("properties", {})
    if isinstance(props, dict) and len(props) > 1:
        return 0.95
    if type_info.get("slots"):
        return 0.9
    return 0.75


def _attribute_confidence(type_info: dict) -> float:
    """Confidence for attribute classification."""
    if type_info.get("type") in ("string", "integer", "number", "boolean"):
        return 0.9
    if type_info.get("$ref"):
        return 0.85  # reference to another class — attribute with type_ref
    return 0.6  # uncertain
