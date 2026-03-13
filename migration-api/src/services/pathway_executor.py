"""PathwayExecutor: executes a migration pathway step by step."""

from __future__ import annotations

import logging
import time

from src.models import MigrationReport, StepResult, ValidationResult, Violation
from src.services.backend_client import BackendClient
from src.services.expression_eval import EvalError, ExpressionEvaluator

logger = logging.getLogger(__name__)


class PathwayExecutor:
    """Execute a migration pathway record by record."""

    def __init__(self, client: BackendClient) -> None:
        self._client = client
        self._evaluator = ExpressionEvaluator()

    async def execute(
        self,
        pathway_id: str,
        input_record: dict,
    ) -> MigrationReport:
        """
        Execute all steps in the pathway against input_record.

        Returns a MigrationReport with per-step results and overall status.
        """
        start = time.monotonic()
        pathway = await self._client.get_pathway(pathway_id)

        steps = pathway.get("steps") or []
        source_schema_id = pathway.get("source_schema_id", "")
        target_schema_id = pathway.get("target_schema_id", "")

        output_record: dict = {}
        step_results: list[StepResult] = []
        mapped_input_fields: set[str] = set()
        any_error = False

        for step_def in sorted(steps, key=lambda s: s.get("position", 0)):
            mapping_id = step_def["mapping_id"]
            position = step_def.get("position", 0)

            try:
                mapping = await self._client.get_mapping(mapping_id)
            except Exception as exc:
                step_results.append(
                    StepResult(
                        position=position,
                        mapping_id=mapping_id,
                        output_element="",
                        input_values={},
                        output_value=None,
                        status="ERROR",
                        error_message=f"Cannot fetch mapping: {exc}",
                    )
                )
                any_error = True
                continue

            cv = mapping.get("current_version") or {}
            expression = cv.get("expression", "input_0")
            expression_type = cv.get("expression_type", "identity")

            # Gather input element names for this step
            inputs_meta = mapping.get("inputs") or []
            # Build positional args: input_0, input_1, ...
            input_values: dict = {}
            for inp in sorted(inputs_meta, key=lambda x: x.get("position", 0)):
                elem_id = str(inp.get("element_id", ""))
                # Try to match input field by element id or fallback to record values
                # Use the record field matching the element position
                pos_key = f"input_{inp.get('position', 0)}"
                # Look up the element name to find the right field
                field_name = self._find_field_for_element(elem_id, input_record, inputs_meta)
                if field_name:
                    input_values[pos_key] = input_record.get(field_name)
                    mapped_input_fields.add(field_name)

            # If no inputs metadata, use first record value
            if not input_values and input_record:
                first_key = next(iter(input_record))
                input_values["input_0"] = input_record[first_key]
                mapped_input_fields.add(first_key)

            # Determine output element name
            output_element = mapping.get("name", f"output_{position}")

            try:
                output_value = self._evaluator.evaluate(
                    expression=expression,
                    expression_type=expression_type,
                    input_values=input_values,
                )
                output_record[output_element] = output_value
                step_results.append(
                    StepResult(
                        position=position,
                        mapping_id=mapping_id,
                        output_element=output_element,
                        input_values=input_values,
                        output_value=output_value,
                        status="OK",
                    )
                )
            except (EvalError, Exception) as exc:
                logger.error("Step %d error: %s", position, exc)
                step_results.append(
                    StepResult(
                        position=position,
                        mapping_id=mapping_id,
                        output_element=output_element,
                        input_values=input_values,
                        output_value=None,
                        status="ERROR",
                        error_message=str(exc),
                    )
                )
                any_error = True

        # Compute passthrough fields (unmapped input fields)
        passthrough_fields = [f for f in input_record if f not in mapped_input_fields]
        if passthrough_fields:
            logger.warning("Unmapped fields passed through: %s", passthrough_fields)
            for field in passthrough_fields:
                output_record[field] = input_record[field]

        # Overall status
        if any_error:
            overall_status = "FAIL"
        elif passthrough_fields:
            overall_status = "PARTIAL"
        else:
            overall_status = "PASS"

        validation_result = await self._validate_output(output_record, target_schema_id)
        if validation_result.status == "FAIL":
            overall_status = "FAIL"

        duration_ms = int((time.monotonic() - start) * 1000)

        return MigrationReport(
            pathway_id=pathway_id,
            source_schema_id=source_schema_id,
            target_schema_id=target_schema_id,
            overall_status=overall_status,
            steps_applied=step_results,
            passthrough_fields=passthrough_fields,
            validation_result=validation_result,
            duration_ms=duration_ms,
        )

    async def _validate_output(
        self,
        output_record: dict,
        target_schema_id: str,
    ) -> ValidationResult:
        """Validate output_record fields against the target schema's known slots."""
        violations: list[Violation] = []
        try:
            elements = await self._client.get_schema_elements(target_schema_id)
            known_names = {e["name"] for e in elements}
            for field_name in output_record:
                if field_name not in known_names:
                    violations.append(
                        Violation(
                            field=field_name,
                            violation_type="unknown_field",
                            severity="WARNING",
                            message=f"Field '{field_name}' not defined in target schema",
                        )
                    )
            status = "PASS" if not violations else "PARTIAL"
        except Exception as exc:
            logger.warning("Could not validate output against target schema %s: %s", target_schema_id, exc)
            status = "UNKNOWN"
        return ValidationResult(status=status, violations=violations)

    def _find_field_for_element(
        self,
        element_id: str,
        record: dict,
        inputs_meta: list[dict],
    ) -> str | None:
        """Try to find the record field corresponding to an element_id."""
        # Simple heuristic: return first record field
        # In production, the element name would be looked up from the backend
        if record:
            return next(iter(record), None)
        return None
