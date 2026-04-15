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
    aliases: list[str] | None = None,
    minimum_value: float | None = None,
    maximum_value: float | None = None,
    prompt: str | None = None,
) -> None:
    """Add a slot to the schema if not already present.

    Args:
        aliases: Alternative names for this slot. SchemaView uses these
                 to resolve alias-based lookups to the canonical slot.
        minimum_value: Minimum numeric value constraint.
        maximum_value: Maximum numeric value constraint.
        prompt: Data collection prompt — the instruction or question presented
                to the person/process filling this field. Carries semantic meaning
                beyond the description (e.g., "Enter the physical pixel size for
                this grid image (in x,y order)"). Stored as a LinkML annotation
                and included in embedding computation for alignment.
    """
    from linkml_runtime.linkml_model import SlotDefinition

    if name in schema.slots:
        # If the slot exists, merge aliases into the existing slot
        existing = schema.slots[name]
        if aliases:
            existing_aliases = list(existing.aliases) if existing.aliases else []
            for a in aliases:
                if a not in existing_aliases and a != name:
                    existing_aliases.append(a)
            existing.aliases = existing_aliases
        return
    slot = SlotDefinition(
        name=name,
        range=range,
        description=description[:500] if description else None,
        required=required or None,
        multivalued=multivalued or None,
    )
    if aliases:
        slot.aliases = [a for a in aliases if a != name]
    if unit:
        slot.annotations["unit"] = unit
    if pattern:
        slot.pattern = pattern
    if minimum_value is not None:
        slot.minimum_value = minimum_value
    if maximum_value is not None:
        slot.maximum_value = maximum_value
    if prompt:
        slot.annotations["prompt"] = prompt
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
