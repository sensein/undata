"""ValidationService — validates data records against a LinkML schema."""

from __future__ import annotations

import enum
import json

from undata.logging import get_logger

logger = get_logger(__name__)


class ViolationSeverity(enum.StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


class Violation:
    def __init__(self, field: str, message: str, severity: ViolationSeverity) -> None:
        self.field = field
        self.message = message
        self.severity = severity

    def to_dict(self) -> dict:
        return {"field": self.field, "message": self.message, "severity": self.severity.value}


def _load_schema(schema_path: str):
    from linkml_runtime.linkml_model.meta import SchemaDefinition
    from linkml_runtime.loaders import yaml_loader

    return yaml_loader.load(schema_path, target_class=SchemaDefinition)


class ValidationService:
    def __init__(
        self,
        schema_path: str | None = None,
        target_class: str = "NeuroscienceDataset",
    ) -> None:
        self._schema_path = schema_path
        self._target_class = target_class
        self._schema = None
        if schema_path:
            self._schema = _load_schema(schema_path)

    def _get_class_def(self, schema, class_name: str):
        return schema.classes.get(class_name)

    def validate(self, record: dict) -> dict:
        violations: list[Violation] = []

        if self._schema is None:
            logger.error("No schema loaded for validation")
            return {
                "status": "FAIL",
                "violations": [
                    {"field": "_schema", "message": "No schema loaded", "severity": "ERROR"}
                ],
            }

        class_def = self._get_class_def(self._schema, self._target_class)
        if class_def is None:
            logger.warning("Target class not found", extra={"class": self._target_class})
            return {
                "status": "FAIL",
                "violations": [
                    {
                        "field": "_class",
                        "message": f"Class {self._target_class!r} not found",
                        "severity": "ERROR",
                    }
                ],
            }

        # Collect all slots for this class (including inherited)
        slot_names = list(class_def.slots)

        for slot_name in slot_names:
            slot_def = self._schema.slots.get(slot_name)
            if slot_def is None:
                continue

            value = record.get(slot_name)

            # Required field check (ERROR)
            if slot_def.required and (value is None or value == ""):
                violations.append(
                    Violation(
                        field=slot_name,
                        message=f"Required field '{slot_name}' is missing or empty.",
                        severity=ViolationSeverity.ERROR,
                    )
                )
                continue

            if value is None:
                continue

            # Enum membership check (ERROR)
            range_name = slot_def.range
            if range_name and range_name in self._schema.enums:
                enum_def = self._schema.enums[range_name]
                allowed = set(enum_def.permissible_values.keys())
                if str(value) not in allowed:
                    violations.append(
                        Violation(
                            field=slot_name,
                            message=(
                                f"Value {value!r} not in allowed values for '{slot_name}': "
                                f"{sorted(allowed)}"
                            ),
                            severity=ViolationSeverity.ERROR,
                        )
                    )

            # Type check (WARNING)
            if range_name in ("float", "integer", "int") and not isinstance(value, (int, float)):
                violations.append(
                    Violation(
                        field=slot_name,
                        message=(
                            f"Field '{slot_name}' expected numeric type,"
                            f" got {type(value).__name__}."
                        ),
                        severity=ViolationSeverity.WARNING,
                    )
                )

        status = (
            "FAIL" if any(v.severity == ViolationSeverity.ERROR for v in violations) else "PASS"
        )
        logger.info("Validation complete", extra={"status": status, "violations": len(violations)})
        return {
            "status": status,
            "violations": [v.to_dict() for v in violations],
        }

    def to_json(self, report: dict) -> str:
        return json.dumps(report, indent=2)

    def to_text(self, report: dict) -> str:
        lines = [f"Validation result: {report['status']}"]
        for v in report.get("violations", []):
            lines.append(f"  [{v['severity']}] {v['field']}: {v['message']}")
        if not report.get("violations"):
            lines.append("  No violations found.")
        return "\n".join(lines)
