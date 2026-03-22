"""BIDS schema adapter — converts bidsschematools to LinkML, then extracts entities.

Architecture: build a LinkML SchemaDefinition programmatically from the BIDS
schema, then use the standard LinkML adapter to extract entities. This ensures
correct entity classification (classes, slots, enums) without ad-hoc logic.

The BIDS schema has three layers:
1. objects/ — field definitions (metadata, columns, entities, enums)
2. rules/sidecars/ — which fields apply to which modality (class-property membership)
3. rules/tabular_data/ — which columns apply to which TSV type
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from ..models import SourceRef
from .base import BaseAdapter, ClassifiedEntity

_TYPE_MAP = {
    "string": "string",
    "number": "float",
    "integer": "integer",
    "boolean": "boolean",
    "array": "string",
    "object": "string",
}


class BIDSAdapter(BaseAdapter):
    @property
    def name(self) -> str:
        return "bids"

    @property
    def supported_formats(self) -> list[str]:
        return []

    def extract(self, source_path: Path, **options: Any) -> list[ClassifiedEntity]:
        try:
            from bidsschematools import schema as bids_schema
        except ImportError as exc:
            raise ImportError(f"bidsschematools required for BIDS extraction: {exc}") from exc

        schema = bids_schema.load_schema()
        base_ref = self._build_source_ref(source_path)

        # Build LinkML schema from BIDS
        linkml_schema = self._build_linkml_schema(schema)

        # Extract entities via LinkML adapter
        from .linkml import LinkMLAdapter

        linkml_adapter = LinkMLAdapter()
        entities = linkml_adapter.extract_from_schema_definition(
            linkml_schema, source_name="bids", source_ref=base_ref
        )

        return entities

    def _build_linkml_schema(self, schema: Any) -> Any:
        """Convert bidsschematools schema to a LinkML SchemaDefinition."""
        from linkml_runtime.linkml_model import (
            EnumDefinition,
            PermissibleValue,
            Prefix,
            SchemaDefinition,
            SlotDefinition,
        )

        objects = schema.get("objects", {})
        sidecars = schema.get("rules", {}).get("sidecars", {})
        tabular = schema.get("rules", {}).get("tabular_data", {})

        ld = SchemaDefinition(
            id="https://bids-specification.readthedocs.io/schema",
            name="bids",
            title="BIDS Specification Schema",
            description="Auto-generated LinkML from BIDS schema via bidsschematools",
            default_range="string",
        )
        ld.prefixes["bids"] = Prefix("bids", "https://bids-specification.readthedocs.io/schema/")
        ld.prefixes["linkml"] = Prefix("linkml", "https://w3id.org/linkml/")

        # 1. Slots from metadata objects
        metadata = objects.get("metadata", {})
        self._add_slots_from_objects(ld, metadata, "metadata")

        # 2. Slots from columns objects
        columns = objects.get("columns", {})
        self._add_slots_from_objects(ld, columns, "columns")

        # 3. Slots from entities objects (filename components)
        entities_cat = objects.get("entities", {})
        for fname in entities_cat:
            if fname in ld.slots:
                continue
            fdef = entities_cat[fname]
            if not hasattr(fdef, "get"):
                continue
            fmt = str(fdef.get("format", "label"))
            dt = "integer" if fmt == "index" else "string"
            slot = SlotDefinition(
                name=fname,
                range=dt,
                description=str(fdef.get("description", "") or "")[:500] or None,
            )
            entity_name = fdef.get("name", fname)
            if entity_name:
                slot.annotations["bids_entity_name"] = str(entity_name)
            slot.annotations["bids_category"] = "entities"
            ld.slots[fname] = slot

        # 4. Enums from objects.enums
        enums_cat = objects.get("enums", {})
        self._add_enums(ld, enums_cat)

        # 5. Enums from vocabulary categories (datatypes, modalities, suffixes, extensions)
        for cat_name in ("datatypes", "modalities", "suffixes", "extensions", "formats"):
            vocab = objects.get(cat_name, {})
            if not vocab:
                continue
            ed = EnumDefinition(
                name=cat_name,
                description=f"BIDS {cat_name} vocabulary",
            )
            for vname in vocab:
                vdef = vocab[vname]
                if not hasattr(vdef, "get") or vname.startswith("_"):
                    continue
                value = str(vdef.get("value", vname))
                display = str(vdef.get("display_name", "") or "")
                pv = PermissibleValue(text=value)
                if display:
                    pv.description = display
                ed.permissible_values[vname] = pv
            if ed.permissible_values:
                ld.enums[cat_name] = ed

        # 6. Classes from sidecar rules — field groups as mixins, modalities as concrete
        for modality in sorted(sidecars.keys()):
            groups = sidecars[modality]
            if not hasattr(groups, "keys"):
                continue
            self._add_sidecar_classes(ld, modality, groups)

        # 7. Classes from tabular_data rules
        for table_name in sorted(tabular.keys()):
            groups = tabular[table_name]
            if not hasattr(groups, "keys"):
                continue
            self._add_tabular_classes(ld, table_name, groups)

        return ld

    def _add_slots_from_objects(self, ld: Any, objects_cat: Any, category: str) -> None:
        """Add slots from a BIDS objects category (metadata or columns)."""
        from linkml_runtime.linkml_model import (
            EnumDefinition,
            PermissibleValue,
            SlotDefinition,
        )

        for fname in objects_cat:
            if fname in ld.slots or fname.startswith("_"):
                continue
            fdef = objects_cat[fname]
            if not hasattr(fdef, "get"):
                continue

            t = fdef.get("type", "string")
            if isinstance(t, (list, tuple)):
                t = t[0] if t else "string"

            slot = SlotDefinition(
                name=fname,
                range=_TYPE_MAP.get(str(t), "string"),
                description=str(fdef.get("description", "") or "")[:500] or None,
            )

            # Unit
            unit = fdef.get("unit")
            if unit:
                slot.annotations["unit"] = str(unit)

            # Pattern
            pattern = fdef.get("pattern")
            if pattern:
                slot.pattern = str(pattern)

            # Enum values → create enum and set range
            enum_vals = fdef.get("enum")
            if enum_vals and hasattr(enum_vals, "__iter__"):
                vals = [str(v) for v in enum_vals if v is not None]
                if vals:
                    enum_name = f"{fname}Enum"
                    ed = EnumDefinition(name=enum_name)
                    for v in vals:
                        ed.permissible_values[v] = PermissibleValue(text=v)
                    ld.enums[enum_name] = ed
                    slot.range = enum_name

            slot.annotations["bids_category"] = category
            ld.slots[fname] = slot

    def _add_enums(self, ld: Any, enums_cat: Any) -> None:
        """Add enums from objects.enums — valuesets and individual values."""
        from linkml_runtime.linkml_model import EnumDefinition, PermissibleValue

        for ename in enums_cat:
            edef = enums_cat[ename]
            if not hasattr(edef, "get"):
                continue

            if ename.startswith("_"):
                # Valueset
                enum_vals = edef.get("enum", [])
                if not enum_vals:
                    continue
                clean_name = ename.lstrip("_")
                if clean_name in ld.enums:
                    continue
                ed = EnumDefinition(name=clean_name)
                for v in enum_vals:
                    if v is None:
                        continue
                    if isinstance(v, dict):
                        ref = v.get("$ref", "")
                        parts = ref.split(".")
                        text = parts[-2] if len(parts) >= 3 else str(v)
                    else:
                        text = str(v)
                    ed.permissible_values[text] = PermissibleValue(text=text)
                ld.enums[clean_name] = ed
            else:
                # Individual enum value — store in a collector enum
                value = str(edef.get("value", ename))
                display = str(edef.get("display_name", "") or "")
                # These get collected into the vocabulary enums above
                # Also store as individual entries in a "bids_enum_values" enum
                collector = ld.enums.get("bids_enum_values")
                if collector is None:
                    from linkml_runtime.linkml_model import EnumDefinition as ED

                    collector = ED(
                        name="bids_enum_values",
                        description="Individual BIDS enum values",
                    )
                    ld.enums["bids_enum_values"] = collector
                pv = PermissibleValue(text=value)
                if display:
                    pv.description = display
                collector.permissible_values[ename] = pv

    def _add_sidecar_classes(self, ld: Any, modality: str, groups: Any) -> None:
        """Add mixin classes from sidecar field groups + concrete modality class."""
        from linkml_runtime.linkml_model import ClassDefinition, SlotDefinition

        mixin_names = []
        for group_name, group in groups.items():
            if not hasattr(group, "get"):
                continue
            fields = group.get("fields", {})
            if not hasattr(fields, "keys") or not fields:
                continue

            mixin = ClassDefinition(
                name=group_name,
                mixin=True,
                description=f"Sidecar field group for {modality}",
            )
            selectors = group.get("selectors", [])
            if selectors:
                mixin.annotations["bids_selectors"] = str(selectors)

            for fname, fdef in fields.items():
                mixin.slots.append(fname)
                # Ensure slot exists (may reference metadata not in objects)
                if fname not in ld.slots:
                    from linkml_runtime.linkml_model import SlotDefinition as SD

                    ld.slots[fname] = SD(name=fname, range="string")

                level = fdef if isinstance(fdef, str) else fdef.get("level", "optional")
                if level == "required":
                    mixin.slot_usage[fname] = SlotDefinition(name=fname, required=True)
                elif level == "recommended":
                    mixin.slot_usage[fname] = SlotDefinition(name=fname, recommended=True)

            ld.classes[group_name] = mixin
            mixin_names.append(group_name)

        if mixin_names:
            concrete = ClassDefinition(
                name=f"{modality}_sidecar",
                description=f"BIDS sidecar metadata for {modality} datatype",
                mixins=mixin_names,
            )
            ld.classes[f"{modality}_sidecar"] = concrete

    def _add_tabular_classes(self, ld: Any, table_name: str, groups: Any) -> None:
        """Add classes from tabular_data column groups."""
        from linkml_runtime.linkml_model import ClassDefinition, SlotDefinition

        mixin_names = []
        for group_name, group in groups.items():
            if not hasattr(group, "get"):
                continue
            cols = group.get("columns", group.get("fields", {}))
            if not hasattr(cols, "keys") or not cols:
                continue

            mixin = ClassDefinition(
                name=f"{table_name}_{group_name}",
                mixin=True,
                description=f"Tabular columns for {table_name}",
            )

            for cname, cdef in cols.items():
                mixin.slots.append(cname)
                if cname not in ld.slots:
                    from linkml_runtime.linkml_model import SlotDefinition as SD

                    ld.slots[cname] = SD(name=cname, range="string")

                level = cdef if isinstance(cdef, str) else cdef.get("level", "optional")
                if level == "required":
                    mixin.slot_usage[cname] = SlotDefinition(name=cname, required=True)

            ld.classes[f"{table_name}_{group_name}"] = mixin
            mixin_names.append(f"{table_name}_{group_name}")

        if mixin_names:
            concrete = ClassDefinition(
                name=f"{table_name}_table",
                description=f"BIDS tabular data for {table_name}",
                mixins=mixin_names,
            )
            ld.classes[f"{table_name}_table"] = concrete

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
        return SourceRef(
            repo=repo,
            committish=committish,
            file="schema",
            checksum="",
        )
