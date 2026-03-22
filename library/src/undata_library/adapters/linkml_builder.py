"""Shared LinkML schema builder helpers for source adapters.

Each adapter converts its native format to a LinkML SchemaDefinition.
This module provides helper functions for common operations.
"""

from __future__ import annotations

from typing import Any


def build_schema(
    name: str,
    schema_id: str,
    title: str | None = None,
    description: str | None = None,
    prefix: str | None = None,
    prefix_uri: str | None = None,
) -> Any:
    """Create a new LinkML SchemaDefinition."""
    from linkml_runtime.linkml_model import Prefix, SchemaDefinition

    ld = SchemaDefinition(
        id=schema_id,
        name=name,
        title=title,
        description=description,
        default_range="string",
    )
    if prefix and prefix_uri:
        ld.prefixes[prefix] = Prefix(prefix, prefix_uri)
    ld.prefixes["linkml"] = Prefix("linkml", "https://w3id.org/linkml/")
    return ld


def add_slot(
    schema: Any,
    name: str,
    range: str = "string",
    description: str | None = None,
    unit: str | None = None,
    pattern: str | None = None,
    required: bool = False,
    multivalued: bool = False,
) -> None:
    """Add a slot to the schema if not already present."""
    from linkml_runtime.linkml_model import SlotDefinition

    if name in schema.slots:
        return
    slot = SlotDefinition(
        name=name,
        range=range,
        description=description[:500] if description else None,
        required=required or None,
        multivalued=multivalued or None,
    )
    if unit:
        slot.annotations["unit"] = unit
    if pattern:
        slot.pattern = pattern
    schema.slots[name] = slot


def add_class(
    schema: Any,
    name: str,
    slots: list[str] | None = None,
    is_a: str | None = None,
    mixins: list[str] | None = None,
    mixin: bool = False,
    description: str | None = None,
    slot_usage: dict[str, dict] | None = None,
) -> None:
    """Add a class to the schema."""
    from linkml_runtime.linkml_model import ClassDefinition, SlotDefinition

    cls = ClassDefinition(
        name=name,
        description=description[:500] if description else None,
        is_a=is_a,
        mixin=mixin or None,
    )
    if mixins:
        cls.mixins = mixins
    if slots:
        cls.slots = slots
    if slot_usage:
        for sname, sdef in slot_usage.items():
            su = SlotDefinition(name=sname)
            if sdef.get("required"):
                su.required = True
            if sdef.get("recommended"):
                su.recommended = True
            cls.slot_usage[sname] = su
    schema.classes[name] = cls


def add_enum(
    schema: Any,
    name: str,
    values: list[str],
    description: str | None = None,
) -> None:
    """Add an enum to the schema if not already present."""
    from linkml_runtime.linkml_model import EnumDefinition, PermissibleValue

    if name in schema.enums:
        return
    ed = EnumDefinition(name=name, description=description)
    for v in values:
        ed.permissible_values[v] = PermissibleValue(text=v)
    schema.enums[name] = ed


def ensure_slot(schema: Any, name: str, range: str = "string") -> None:
    """Ensure a slot exists (create if missing)."""
    if name not in schema.slots:
        add_slot(schema, name, range=range)
