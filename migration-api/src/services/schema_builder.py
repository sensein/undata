"""LinkML SchemaDefinition builder from stored data elements."""

from __future__ import annotations

import logging
from dataclasses import dataclass

import yaml
from linkml_runtime.linkml_model import SchemaDefinition
from linkml_runtime.linkml_model.meta import ClassDefinition, SlotDefinition

from src.services.backend_client import BackendClient, BackendClientError

logger = logging.getLogger(__name__)

# Map data_type strings → LinkML range names
_TYPE_MAP: dict[str, str] = {
    "string": "string",
    "str": "string",
    "text": "string",
    "integer": "integer",
    "int": "integer",
    "float": "float",
    "number": "float",
    "boolean": "boolean",
    "bool": "boolean",
    "date": "date",
    "datetime": "datetime",
    "uri": "uri",
    "uriorcurie": "uriorcurie",
}


class ConflictError(Exception):
    """Raised when element name collisions are detected across source schemas."""

    def __init__(self, message: str, conflicting_names: list[str]) -> None:
        self.conflicting_names = conflicting_names
        super().__init__(message)


@dataclass
class BuildResult:
    name: str
    version: str
    linkml_yaml: str
    linkml_jsonld: str | None = None
    schema_id: str | None = None


class SchemaBuilder:
    """Builds a linkml_runtime SchemaDefinition from stored data elements."""

    def __init__(self, client: BackendClient) -> None:
        self._client = client

    async def build(
        self,
        name: str,
        version: str,
        classes: list[dict],
    ) -> BuildResult:
        """
        Build a SchemaDefinition from element IDs grouped into classes.

        Args:
            name: Schema name.
            version: CalVer version string.
            classes: List of dicts with keys ``name`` and ``element_ids``.

        Returns:
            BuildResult with linkml_yaml and optionally linkml_jsonld.

        Raises:
            ValueError: If any element_id cannot be resolved (lists unknown_ids).
            ConflictError: If the same slot name appears with different types.
        """
        # Collect all element IDs across all classes
        all_ids: list[str] = []
        for cls_spec in classes:
            all_ids.extend(str(eid) for eid in cls_spec["element_ids"])

        # Fetch all elements; collect failures
        elements_by_id: dict[str, dict] = {}
        unknown_ids: list[str] = []

        for eid in all_ids:
            try:
                elem = await self._client.get_element(eid)
                elements_by_id[eid] = elem
            except BackendClientError as exc:
                if exc.status_code == 404:
                    unknown_ids.append(eid)
                else:
                    raise

        if unknown_ids:
            raise ValueError(f"unknown_ids: {unknown_ids}")

        # Build SchemaDefinition
        schema = SchemaDefinition(id=f"https://undata.org/schemas/{name}", name=name)
        schema.version = version

        # Global slot registry — detect name collisions
        global_slots: dict[str, str] = {}  # slot_name → data_type
        conflicts: list[str] = []

        for cls_spec in classes:
            cls_name = cls_spec["name"]
            cls_def = ClassDefinition(cls_name)
            class_slots: list[str] = []

            for eid in (str(i) for i in cls_spec["element_ids"]):
                elem = elements_by_id[eid]
                slot_name = elem.get("name", eid)
                data_type = elem.get("data_type", "string")
                linkml_range = _TYPE_MAP.get(data_type.lower(), "string")

                # Collision detection
                if slot_name in global_slots and global_slots[slot_name] != linkml_range:
                    logger.error(
                        "Name collision for slot %s: existing=%s new=%s (elem %s)",
                        slot_name,
                        global_slots[slot_name],
                        linkml_range,
                        eid,
                    )
                    conflicts.append(slot_name)
                else:
                    global_slots[slot_name] = linkml_range

                slot_def = SlotDefinition(slot_name)
                slot_def.range = linkml_range
                slot_def.description = elem.get("description", "")
                slot_def.required = bool(elem.get("required", False))
                slot_def.multivalued = bool(elem.get("multivalued", False))

                if elem.get("allowed_values"):
                    slot_def.range = slot_name + "_enum"

                schema.slots[slot_name] = slot_def
                class_slots.append(slot_name)

            cls_def.slots = class_slots
            schema.classes[cls_name] = cls_def

        if conflicts:
            raise ConflictError(
                f"Name collision(s) detected: {conflicts}",
                conflicting_names=conflicts,
            )

        # Serialize to YAML
        linkml_yaml = self._schema_to_yaml(schema)

        # Produce a minimal JSON-LD representation
        linkml_jsonld = self._schema_to_jsonld(schema)

        return BuildResult(
            name=name,
            version=version,
            linkml_yaml=linkml_yaml,
            linkml_jsonld=linkml_jsonld,
        )

    def _schema_to_yaml(self, schema: SchemaDefinition) -> str:
        """Serialize SchemaDefinition to YAML string."""
        doc: dict = {
            "id": schema.id,
            "name": schema.name,
            "version": schema.version or "",
            "prefixes": {"linkml": "https://w3id.org/linkml/"},
            "default_prefix": schema.name,
            "imports": ["linkml:types"],
            "slots": {},
            "classes": {},
        }
        for slot_name, slot_def in schema.slots.items():
            doc["slots"][slot_name] = {
                "range": slot_def.range,
                "description": slot_def.description or "",
                "required": slot_def.required,
                "multivalued": slot_def.multivalued,
            }
        for cls_name, cls_def in schema.classes.items():
            doc["classes"][cls_name] = {
                "slots": list(cls_def.slots or []),
            }
        return yaml.dump(doc, default_flow_style=False, allow_unicode=True)

    def _schema_to_jsonld(self, schema: SchemaDefinition) -> str:
        """Produce a minimal JSON-LD context for the schema."""
        import json

        ctx: dict = {
            "@context": {
                "@vocab": f"https://undata.org/schemas/{schema.name}/",
                "linkml": "https://w3id.org/linkml/",
            },
            "@graph": [
                {
                    "@id": schema.id,
                    "@type": "linkml:SchemaDefinition",
                    "linkml:name": schema.name,
                    "linkml:version": schema.version,
                }
            ],
        }
        return json.dumps(ctx, indent=2)
