"""LLM-assisted entity classification via litellm."""

from __future__ import annotations

import json
import logging
from typing import Any

from ..models import EntityType

logger = logging.getLogger(__name__)

_CLASSIFICATION_PROMPT = """Classify this schema entity as one of: class, attribute, enum_value, valueset.

Entity: {name}
Type signature: {type_info}
Description: {description}
Parent class: {parent}
Sibling entities: {siblings}

A "class" has properties/fields defining a shape (like a table or object).
An "attribute" is a single field/property (like a column).
An "enum_value" is a single literal constant value.
A "valueset" is a named collection of enum values (like an enum type).

Respond with JSON only: {{"classification": "class|attribute|enum_value|valueset", "confidence": 0.0-1.0, "reasoning": "..."}}"""


class LLMClassifier:
    """Optional LLM-based entity classifier using litellm."""

    def __init__(self, model: str):
        self.model = model

    def classify(
        self,
        name: str,
        type_info: dict[str, Any],
        description: str = "",
        parent: str | None = None,
        siblings: list[str] | None = None,
    ) -> tuple[EntityType, float, str]:
        """Classify an entity using LLM. Returns (type, confidence, reasoning)."""
        try:
            import litellm
        except ImportError:
            raise ImportError("litellm required for LLM classification: pip install litellm")

        prompt = _CLASSIFICATION_PROMPT.format(
            name=name,
            type_info=json.dumps(type_info, default=str)[:500],  # Truncate large schemas
            description=description or "N/A",
            parent=parent or "N/A",
            siblings=", ".join(siblings[:10]) if siblings else "N/A",
        )

        try:
            response = litellm.completion(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.0,
                max_tokens=200,
            )
            content = response.choices[0].message.content.strip()

            # Parse JSON response
            result = json.loads(content)
            classification = result.get("classification", "").lower()
            confidence = float(result.get("confidence", 0.5))
            reasoning = result.get("reasoning", "")

            # Validate against EntityType
            try:
                etype = EntityType(classification)
            except ValueError:
                logger.warning(
                    "LLM returned invalid classification '%s' for %s", classification, name
                )
                raise ValueError(f"Invalid classification: {classification}")

            return etype, min(1.0, max(0.0, confidence)), reasoning

        except (json.JSONDecodeError, KeyError, ValueError) as exc:
            logger.warning("LLM classification failed for %s: %s", name, exc)
            raise
        except Exception as exc:
            logger.warning("LLM API error for %s: %s", name, exc)
            raise
