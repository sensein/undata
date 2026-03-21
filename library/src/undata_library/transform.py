"""Transform generation engine — detect patterns and create typed bidirectional transforms."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .hashing import canonical_json, compute_sha256, generate_short_key
from .models import FunctionSpec, MappingFunctionType, ProvenanceEntry, TransformRecord

logger = logging.getLogger(__name__)

# Known unit conversion factors: (unit_a, unit_b) → factor (a * factor = b)
_UNIT_CONVERSIONS: dict[tuple[str, str], float] = {
    ("year", "month"): 12.0,
    ("month", "year"): 1.0 / 12.0,
    ("meter", "centimeter"): 100.0,
    ("centimeter", "meter"): 0.01,
    ("kilogram", "gram"): 1000.0,
    ("gram", "kilogram"): 0.001,
    ("second", "millisecond"): 1000.0,
    ("millisecond", "second"): 0.001,
}


def generate_transforms(
    elements_dir: Path,
    library_path: Path,
    threshold: float = 0.5,
) -> dict[str, int]:
    """Generate transforms between elements sharing ontology_term but differing in type/unit.

    Returns stats: {pairs_evaluated, transforms_created, patterns: {identity, unit_conversion, ...}}
    """
    transforms_dir = library_path / "transforms"
    transforms_dir.mkdir(parents=True, exist_ok=True)

    # Group elements by ontology_term
    by_onto: dict[str, list[tuple[str, dict]]] = {}
    for f in sorted(elements_dir.glob("*.yaml")):
        try:
            data = yaml.safe_load(f.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or "semantic" not in data:
                continue
        except (yaml.YAMLError, OSError):
            continue

        onto = data["semantic"].get("ontology_term")
        if not onto:
            continue

        uri = f"https://schema.undata.live/elements/{f.stem}"
        by_onto.setdefault(onto, []).append((uri, data))

    stats = {
        "pairs_evaluated": 0,
        "transforms_created": 0,
        "patterns": {t.value: 0 for t in MappingFunctionType},
    }

    existing = {f.stem for f in transforms_dir.glob("*.yaml")}
    now_iso = datetime.now(timezone.utc).isoformat()

    for onto_term, elements in by_onto.items():
        n = len(elements)
        for i in range(n):
            uri_a, data_a = elements[i]
            for j in range(i + 1, n):
                uri_b, data_b = elements[j]
                stats["pairs_evaluated"] += 1

                sem_a = data_a["semantic"]
                sem_b = data_b["semantic"]

                # Skip same-hash pairs (identical semantic = no transform needed)
                can_a = canonical_json(sem_a)
                can_b = canonical_json(sem_b)
                if compute_sha256(can_a) == compute_sha256(can_b):
                    continue

                # Detect pattern
                func_spec = _detect_pattern(sem_a, sem_b)
                if func_spec is None:
                    continue

                # Write forward transform: A → B
                _write_transform(uri_a, uri_b, func_spec, transforms_dir, existing, now_iso)
                stats["transforms_created"] += 1
                stats["patterns"][func_spec.function_type.value] += 1

                # Write reverse transform: B → A
                reverse_spec = _reverse_function(func_spec)
                _write_transform(uri_b, uri_a, reverse_spec, transforms_dir, existing, now_iso)
                stats["transforms_created"] += 1

    return stats


def _detect_pattern(sem_a: dict, sem_b: dict) -> FunctionSpec | None:
    """Detect the conversion pattern between two semantic identities."""
    type_a = sem_a.get("data_type", "string")
    type_b = sem_b.get("data_type", "string")
    unit_a = sem_a.get("unit")
    unit_b = sem_b.get("unit")

    # Value mapping: overlapping enums/response_options (check before identity)
    opts_a = _extract_values(sem_a)
    opts_b = _extract_values(sem_b)
    if opts_a and opts_b and set(opts_a) != set(opts_b):
        shared = set(opts_a) & set(opts_b)
        total = set(opts_a) | set(opts_b)
        if total and len(shared) / len(total) > 0.3:
            lookup = {v: v for v in sorted(shared)}
            return FunctionSpec(
                function_type=MappingFunctionType.value_mapping,
                input_type=type_a,
                output_type=type_b,
                expression=json.dumps(lookup),
                expression_type="lookup_table",
                parameters={"shared_count": len(shared), "total_count": len(total)},
            )

    # Identity: same type, same unit, same value set
    if type_a == type_b and unit_a == unit_b:
        return FunctionSpec(
            function_type=MappingFunctionType.identity,
            input_type=type_a,
            output_type=type_b,
            expression_type="none",
        )

    # Unit conversion: same type, different unit
    if type_a == type_b and unit_a and unit_b:
        factor = _UNIT_CONVERSIONS.get((unit_a, unit_b))
        if factor is not None:
            return FunctionSpec(
                function_type=MappingFunctionType.unit_conversion,
                input_type=type_a,
                output_type=type_b,
                expression=f"value * {factor}",
                expression_type="arithmetic",
                parameters={"factor": factor, "unit_from": unit_a, "unit_to": unit_b},
            )

    # Type conversion: float ↔ string (ISO8601 duration)
    if _is_numeric(type_a) and type_b == "string" and _is_iso8601_context(sem_b):
        return FunctionSpec(
            function_type=MappingFunctionType.type_conversion,
            input_type=type_a,
            output_type=type_b,
            expression="iso8601_duration_from_years",
            expression_type="named_function",
        )
    if type_a == "string" and _is_numeric(type_b) and _is_iso8601_context(sem_a):
        return FunctionSpec(
            function_type=MappingFunctionType.type_conversion,
            input_type=type_a,
            output_type=type_b,
            expression="years_from_iso8601_duration",
            expression_type="named_function",
        )

    # Structural: object ↔ primitive
    if (type_a == "object" and type_b != "object") or (type_a != "object" and type_b == "object"):
        return FunctionSpec(
            function_type=MappingFunctionType.structural,
            input_type=type_a,
            output_type=type_b,
            expression_type="template",
        )

    # Different types, unknown relation
    if type_a != type_b:
        return FunctionSpec(
            function_type=MappingFunctionType.unknown,
            input_type=type_a,
            output_type=type_b,
            expression_type="none",
        )

    return None


def _reverse_function(func: FunctionSpec) -> FunctionSpec:
    """Create the reverse function spec (B → A)."""
    if func.function_type == MappingFunctionType.identity:
        return FunctionSpec(
            function_type=MappingFunctionType.identity,
            input_type=func.output_type,
            output_type=func.input_type,
            expression_type="none",
        )

    if func.function_type == MappingFunctionType.unit_conversion and func.parameters:
        factor = func.parameters.get("factor", 1.0)
        reverse_factor = 1.0 / factor if factor != 0 else 0
        return FunctionSpec(
            function_type=MappingFunctionType.unit_conversion,
            input_type=func.output_type,
            output_type=func.input_type,
            expression=f"value * {reverse_factor}",
            expression_type="arithmetic",
            parameters={
                "factor": reverse_factor,
                "unit_from": func.parameters.get("unit_to"),
                "unit_to": func.parameters.get("unit_from"),
            },
        )

    if func.function_type == MappingFunctionType.type_conversion:
        # Swap named function
        reverse_expr = None
        if func.expression == "iso8601_duration_from_years":
            reverse_expr = "years_from_iso8601_duration"
        elif func.expression == "years_from_iso8601_duration":
            reverse_expr = "iso8601_duration_from_years"
        return FunctionSpec(
            function_type=MappingFunctionType.type_conversion,
            input_type=func.output_type,
            output_type=func.input_type,
            expression=reverse_expr,
            expression_type=func.expression_type,
        )

    # For value_mapping, structural, unknown — swap types, keep same expression
    return FunctionSpec(
        function_type=func.function_type,
        input_type=func.output_type,
        output_type=func.input_type,
        expression=func.expression,
        expression_type=func.expression_type,
        parameters=func.parameters,
    )


def _write_transform(
    source_uri: str,
    target_uri: str,
    func_spec: FunctionSpec,
    transforms_dir: Path,
    existing: set[str],
    now_iso: str,
) -> None:
    """Write a single transform YAML file."""
    # Content-addressed hash from source + target + function
    identity = {
        "source_element": source_uri,
        "target_element": target_uri,
        "function": func_spec.model_dump(exclude_none=True),
    }
    canonical = canonical_json(identity)
    sha = compute_sha256(canonical)
    key = generate_short_key(sha)

    # Derive names for filename
    src_name = source_uri.rsplit("/", 1)[-1].rsplit("_", 1)[0]
    tgt_name = target_uri.rsplit("/", 1)[-1].rsplit("_", 1)[0]
    filename = f"{src_name}_to_{tgt_name}_{key}"

    if filename in existing:
        return

    record = TransformRecord(
        source_element=source_uri,
        target_element=target_uri,
        function=func_spec,
        provenance=[
            ProvenanceEntry(
                source="auto",
                **{"class": ""},
                name="",
                generated_at=now_iso,
                attributed_to="urn:undata:transform-pipeline",
                activity="transform",
            ),
        ],
    )

    data = record.model_dump(mode="json", exclude_none=True, by_alias=True)
    data["sha256"] = sha

    (transforms_dir / f"{filename}.yaml").write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    existing.add(filename)


def _is_numeric(dt: str) -> bool:
    return dt in ("integer", "float")


def _is_iso8601_context(sem: dict) -> bool:
    """Check if the element has ISO8601 duration context."""
    unit = sem.get("unit", "")
    if unit and "iso8601" in unit.lower():
        return True
    # Check if any hint of ISO8601 in the semantic
    for key in ("unit", "value_domain"):
        val = sem.get(key, "")
        if val and "iso" in str(val).lower():
            return True
    return False


def _extract_values(sem: dict) -> list[str]:
    """Extract enum/response_option values for comparison."""
    opts = sem.get("response_options", [])
    if opts:
        return [o.get("value", "") for o in opts if isinstance(o, dict)]
    constraints = sem.get("constraints", {})
    if constraints and constraints.get("allowed_values"):
        return constraints["allowed_values"]
    return []
