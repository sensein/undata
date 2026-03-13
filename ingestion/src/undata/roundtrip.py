"""Roundtrip fidelity functions for JSON Schema and LinkML schemas."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass, field
from pathlib import Path

from linkml_runtime.dumpers import yaml_dumper
from linkml_runtime.linkml_model import SchemaDefinition
from linkml_runtime.linkml_model.meta import ClassDefinition, SlotDefinition

from undata.adapters.json_schema import GenericJSONSchemaAdapter
from undata.adapters.linkml_adapter import LinkMLAdapter
from undata.logging import get_logger
from undata.models import NormalizedElement, SchemaClassPayload

logger = get_logger(__name__)

# Reverse map: data_type → LinkML range
_TYPE_TO_RANGE: dict[str, str] = {
    "string": "string",
    "number": "float",
    "boolean": "boolean",
    "object": "Any",
    "array": "string",  # multivalued=True handles the array aspect
}


@dataclass
class RoundtripResult:
    """Result of a roundtrip fidelity check."""

    fidelity_score: float
    missing_classes: list[str] = field(default_factory=list)
    missing_elements: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _build_schema_def(
    elements: list[NormalizedElement],
    classes: list[SchemaClassPayload],
    schema_name: str = "roundtrip",
) -> SchemaDefinition:
    """Build a minimal SchemaDefinition from extracted elements and classes."""
    sd = SchemaDefinition(id=f"https://example.org/{schema_name}", name=schema_name)

    # Add slots
    for el in elements:
        slot = SlotDefinition(el.name)
        slot.range = _TYPE_TO_RANGE.get(el.data_type, "string")
        slot.required = el.required
        slot.multivalued = el.multivalued
        if el.description:
            slot.description = el.description
        sd.slots[el.name] = slot

    # Add classes
    for cls in classes:
        class_def = ClassDefinition(cls.class_name)
        if cls.description:
            class_def.description = cls.description
        if cls.parent_class_name:
            class_def.is_a = cls.parent_class_name
        # Populate class slots from element_source_local_ids
        class_def.slots = [slid.split(".")[-1] for slid in cls.element_source_local_ids]
        sd.classes[cls.class_name] = class_def

    return sd


def _compare(
    elements_in: list[NormalizedElement],
    classes_in: list[SchemaClassPayload],
    elements_out: list[NormalizedElement],
    classes_out: list[SchemaClassPayload],
) -> RoundtripResult:
    """Compute fidelity score and missing items."""
    names_in = {e.name for e in elements_in}
    names_out = {e.name for e in elements_out}
    classes_in_names = {c.class_name for c in classes_in}
    classes_out_names = {c.class_name for c in classes_out}

    missing_elements = sorted(names_in - names_out)
    missing_classes = sorted(classes_in_names - classes_out_names)

    total = len(names_in) + len(classes_in_names)
    lost = len(missing_elements) + len(missing_classes)
    fidelity_score = 1.0 - lost / max(total, 1)

    return RoundtripResult(
        fidelity_score=fidelity_score,
        missing_elements=missing_elements,
        missing_classes=missing_classes,
        warnings=[],
    )


def roundtrip_json_schema(path: str) -> RoundtripResult:
    """Load a JSON Schema, convert to LinkML YAML, re-import, and measure fidelity.

    Raises:
        ValueError: if path is empty.
        FileNotFoundError: if the file does not exist.
    """
    if not path:
        raise ValueError("path is required for roundtrip_json_schema")

    adapter = GenericJSONSchemaAdapter()
    adapter.load_file(path)
    elements_in = adapter.extract_elements()
    classes_in = adapter.extract_classes()
    cycle_warnings = list(adapter.cycle_warnings)

    if not elements_in and not classes_in:
        return RoundtripResult(fidelity_score=1.0, warnings=cycle_warnings)

    schema_name = Path(path).stem or "roundtrip"
    sd = _build_schema_def(elements_in, classes_in, schema_name)

    yaml_str = yaml_dumper.dumps(sd)

    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as tmp:
        tmp.write(yaml_str)
        tmp_path = tmp.name

    la = LinkMLAdapter()
    la.load_file(tmp_path)
    elements_out = la.extract_elements()
    classes_out = la.extract_classes()

    result = _compare(elements_in, classes_in, elements_out, classes_out)
    result.warnings.extend(cycle_warnings)
    logger.info(
        "Roundtrip JSON Schema complete",
        extra={"fidelity_score": result.fidelity_score, "path": path},
    )
    return result


def roundtrip_linkml(path: str) -> RoundtripResult:
    """Load a LinkML YAML schema, re-serialize, re-import, and measure fidelity.

    Raises:
        ValueError: if path is empty.
        FileNotFoundError / Exception: if the file does not exist or is invalid.
    """
    if not path:
        raise ValueError("path is required for roundtrip_linkml")

    la = LinkMLAdapter()
    la.load_file(path)
    elements_in = la.extract_elements()
    classes_in = la.extract_classes()

    if not elements_in and not classes_in:
        return RoundtripResult(fidelity_score=1.0)

    yaml_str = yaml_dumper.dumps(la._schema)

    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as tmp:
        tmp.write(yaml_str)
        tmp_path = tmp.name

    la2 = LinkMLAdapter()
    la2.load_file(tmp_path)
    elements_out = la2.extract_elements()
    classes_out = la2.extract_classes()

    result = _compare(elements_in, classes_in, elements_out, classes_out)
    logger.info(
        "Roundtrip LinkML complete",
        extra={"fidelity_score": result.fidelity_score, "path": path},
    )
    return result
