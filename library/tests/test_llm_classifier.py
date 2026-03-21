"""Tests for LLM-assisted classification."""

import sys
from unittest.mock import MagicMock, patch


from undata_library.adapters.classifier import classify_entity
from undata_library.models import EntityType

# Create a mock litellm module so imports work even without litellm installed
_mock_litellm = MagicMock()
sys.modules.setdefault("litellm", _mock_litellm)

from undata_library.adapters.llm_classifier import LLMClassifier  # noqa: E402


def _mock_completion(classification: str, confidence: float = 0.9):
    """Create a mock litellm completion response."""
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[
        0
    ].message.content = (
        f'{{"classification": "{classification}", "confidence": {confidence}, "reasoning": "test"}}'
    )
    return mock_response


def test_llm_valid_classification():
    """Mock litellm returns valid classification → accepted."""
    with patch("litellm.completion", return_value=_mock_completion("class", 0.92)):
        llm = LLMClassifier("test-model")
        etype, conf, reasoning = llm.classify("Subject", {"properties": {"a": {}}})
        assert etype == EntityType.CLASS
        assert conf == 0.92
        assert reasoning == "test"


def test_llm_invalid_type_raises():
    """Mock litellm returns invalid type → ValueError."""
    with patch("litellm.completion", return_value=_mock_completion("invalid_type")):
        llm = LLMClassifier("test-model")
        try:
            llm.classify("foo", {})
            assert False, "Should have raised"
        except ValueError:
            pass


def test_llm_disabled_uses_rule_based():
    """LLM disabled (no --llm-model) → rule-based only."""
    etype, conf = classify_entity("age", {"type": "string"}, llm_model=None)
    assert etype == EntityType.ATTRIBUTE
    assert conf >= 0.8


def test_llm_fallback_on_low_confidence():
    """When rule-based confidence < threshold and LLM available, invoke LLM."""
    with patch("litellm.completion", return_value=_mock_completion("valueset", 0.88)):
        # Empty type_info → low rule-based confidence
        etype, conf = classify_entity(
            "unknown_thing", {}, llm_model="test-model", llm_threshold=0.7
        )
        assert etype == EntityType.VALUESET
        assert conf == 0.88


def test_llm_not_invoked_when_confident():
    """When rule-based confidence >= threshold, LLM not invoked."""
    with patch("litellm.completion") as mock_llm:
        etype, conf = classify_entity(
            "age", {"type": "string"}, llm_model="test-model", llm_threshold=0.7
        )
        # String type → 0.9 confidence → no LLM call
        assert etype == EntityType.ATTRIBUTE
        mock_llm.assert_not_called()
