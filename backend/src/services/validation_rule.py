"""ValidationRuleService — typed validation rules with breaking-change classification.

SemanticChangeClassifier (classify function) implements the 6-rule engine from FR-006:
- enum_set: narrowing (remove values) → BREAKING; widening (add values) → NON_BREAKING
- range: tighten min↑ or max↓ → BREAKING; loosen → NON_BREAKING
- pattern: add regex → BREAKING; remove regex → NON_BREAKING
- type_constraint: any type change → BREAKING
- cardinality: increase min or decrease max → BREAKING; otherwise → NON_BREAKING
- unknown rule_type → NON_BREAKING (safe default)
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db import ValidationRule, ValidationRuleChange

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# SemanticChangeClassifier — pure function (T032)
# ---------------------------------------------------------------------------


def classify(rule_type: str, old_value: dict[str, Any], new_value: dict[str, Any]) -> bool:
    """Return True if the change is BREAKING, False if NON_BREAKING.

    A BREAKING change means previously-valid data may become invalid (constraint narrowing).
    A NON_BREAKING change means all previously-valid data remains valid (constraint widening).
    """
    if rule_type == "enum_set":
        old_set = set(old_value.get("values", []))
        new_set = set(new_value.get("values", []))
        # Removing values = narrowing = BREAKING
        return not new_set.issuperset(old_set)

    if rule_type == "range":
        breaking = False
        old_min = old_value.get("min")
        new_min = new_value.get("min")
        old_max = old_value.get("max")
        new_max = new_value.get("max")
        if old_min is not None and new_min is not None:
            breaking = breaking or (new_min > old_min)
        if old_max is not None and new_max is not None:
            breaking = breaking or (new_max < old_max)
        return breaking

    if rule_type == "type_constraint":
        return old_value.get("type") != new_value.get("type")

    if rule_type == "pattern":
        # Adding a regex constraint is narrowing = BREAKING
        # Removing or keeping same regex is widening = NON_BREAKING
        had_regex = "regex" in old_value
        has_regex = "regex" in new_value
        if not had_regex and has_regex:
            return True  # Added new constraint
        if had_regex and has_regex and old_value["regex"] != new_value["regex"]:
            return True  # Changed regex (new constraint replaces old)
        return False

    if rule_type == "cardinality":
        breaking = False
        old_min_count = old_value.get("min_count", 0)
        new_min_count = new_value.get("min_count", 0)
        old_max_count = old_value.get("max_count", 9999)
        new_max_count = new_value.get("max_count", 9999)
        if "min_count" in new_value:
            breaking = breaking or (new_min_count > old_min_count)
        if "max_count" in new_value:
            breaking = breaking or (new_max_count < old_max_count)
        return breaking

    # Unknown rule type — safe default: not breaking
    return False


# ---------------------------------------------------------------------------
# ValidationRuleService (T033)
# ---------------------------------------------------------------------------


class DuplicateRuleError(Exception):
    """Raised when an active rule of the same type already exists for the element."""


class RuleNotFoundError(Exception):
    """Raised when a ValidationRule is not found or is already deleted."""


async def create_rule(
    *,
    element_id: uuid.UUID,
    rule_type: str,
    rule_value: dict[str, Any],
    severity: str = "error",
    description: str | None = None,
    actor_id: uuid.UUID,
    db: AsyncSession,
) -> tuple[ValidationRule, ValidationRuleChange]:
    """Create a ValidationRule and its initial CREATE ValidationRuleChange.

    Raises DuplicateRuleError if an active rule of this type already exists.
    """
    # Check for existing active rule (one active rule per type per element)
    existing = await db.execute(
        select(ValidationRule).where(
            ValidationRule.element_id == element_id,
            ValidationRule.rule_type == rule_type,
            ValidationRule.deleted_at.is_(None),
        )
    )
    if existing.scalar_one_or_none() is not None:
        raise DuplicateRuleError(
            f"Active validation rule of type '{rule_type}' already exists for element {element_id}"
        )

    rule = ValidationRule(
        id=uuid.uuid4(),
        element_id=element_id,
        rule_type=rule_type,
        rule_value=rule_value,
        severity=severity,
        description=description,
        created_by=actor_id,
    )
    db.add(rule)
    await db.flush()

    change = ValidationRuleChange(
        id=uuid.uuid4(),
        rule_id=rule.id,
        element_id=element_id,
        operation="CREATE",
        old_value=None,
        new_value=rule_value,
        breaking=False,  # creating a rule is never breaking
        actor_id=actor_id,
        timestamp=datetime.now(timezone.utc),
        reason=None,
    )
    db.add(change)
    await db.flush()

    logger.info(
        "Created validation rule type='%s'",
        rule_type,
        extra={"element_id": str(element_id), "rule_id": str(rule.id)},
    )
    return rule, change


async def update_rule(
    *,
    rule_id: uuid.UUID,
    new_rule_value: dict[str, Any],
    severity: str | None = None,
    description: str | None = None,
    reason: str | None = None,
    actor_id: uuid.UUID,
    db: AsyncSession,
    schema_changelog_service: Any = None,  # optional; injected to record schema-level changelog
) -> tuple[ValidationRule, ValidationRuleChange]:
    """Update a ValidationRule, classify the change, and record a ValidationRuleChange.

    When breaking=True and schema_changelog_service is provided, inserts a
    SchemaChangeLog entry for every affected schema (operation='RULE_CHANGE').
    """
    result = await db.execute(
        select(ValidationRule).where(
            ValidationRule.id == rule_id,
            ValidationRule.deleted_at.is_(None),
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise RuleNotFoundError(f"ValidationRule {rule_id} not found or deleted")

    old_value = dict(rule.rule_value)
    is_breaking = classify(rule.rule_type, old_value, new_rule_value)

    # Apply update
    rule.rule_value = new_rule_value
    if severity is not None:
        rule.severity = severity
    if description is not None:
        rule.description = description

    change = ValidationRuleChange(
        id=uuid.uuid4(),
        rule_id=rule.id,
        element_id=rule.element_id,
        operation="UPDATE",
        old_value=old_value,
        new_value=new_rule_value,
        breaking=is_breaking,
        actor_id=actor_id,
        timestamp=datetime.now(timezone.utc),
        reason=reason,
    )
    db.add(change)
    await db.flush()

    # If breaking, record SchemaChangeLog for every schema that contains this element
    if is_breaking and schema_changelog_service is not None:
        from src.models.db import DynamicSchemaElement

        schema_result = await db.execute(
            select(DynamicSchemaElement.schema_id).where(
                DynamicSchemaElement.element_id == rule.element_id
            )
        )
        affected_schema_ids = [row[0] for row in schema_result.all()]

        for schema_id in affected_schema_ids:
            await schema_changelog_service.record(
                schema_id=schema_id,
                operation="RULE_CHANGE",
                actor_id=actor_id,
                diff={"rule_id": str(rule.id), "rule_type": rule.rule_type},
                breaking=True,
                reason=reason,
                activity_type="schema_edit",
                semantic_boundary_crossed=True,
                db=db,
            )

    logger.info(
        "Updated validation rule type='%s' breaking=%s",
        rule.rule_type,
        is_breaking,
        extra={"rule_id": str(rule.id)},
    )
    return rule, change


async def delete_rule(
    *,
    rule_id: uuid.UUID,
    actor_id: uuid.UUID,
    reason: str | None = None,
    db: AsyncSession,
) -> tuple[ValidationRule, ValidationRuleChange]:
    """Soft-delete a ValidationRule. Deleting a rule is always NON_BREAKING."""
    result = await db.execute(
        select(ValidationRule).where(
            ValidationRule.id == rule_id,
            ValidationRule.deleted_at.is_(None),
        )
    )
    rule = result.scalar_one_or_none()
    if rule is None:
        raise RuleNotFoundError(f"ValidationRule {rule_id} not found or deleted")

    rule.deleted_at = datetime.now(timezone.utc)

    now = datetime.now(timezone.utc)
    change = ValidationRuleChange(
        id=uuid.uuid4(),
        rule_id=rule.id,
        element_id=rule.element_id,
        operation="DELETE",
        old_value=dict(rule.rule_value),
        new_value=None,
        breaking=False,  # removing a rule is never breaking (relaxes constraints)
        actor_id=actor_id,
        timestamp=now,
        reason=reason,
    )
    db.add(change)
    await db.flush()

    logger.info(
        "Soft-deleted validation rule",
        extra={"rule_id": str(rule.id)},
    )
    return rule, change


async def list_rules(
    *,
    element_id: uuid.UUID,
    db: AsyncSession,
) -> list[ValidationRule]:
    """Return all active (non-deleted) ValidationRules for an element, ordered by rule_type."""
    result = await db.execute(
        select(ValidationRule)
        .where(
            ValidationRule.element_id == element_id,
            ValidationRule.deleted_at.is_(None),
        )
        .order_by(ValidationRule.rule_type)
    )
    return list(result.scalars().all())
