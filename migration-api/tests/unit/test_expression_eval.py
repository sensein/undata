"""Failing unit tests for ExpressionEvaluator — must fail before implementation (TDD).

Tests:
- simpleeval arithmetic expression evaluates correctly
- String concatenation expression evaluates correctly
- Unsafe expressions (import, exec) raise EvalError
- Plugin dispatch to named callable is routed correctly
"""

from __future__ import annotations

import pytest

from src.services.expression_eval import EvalError, ExpressionEvaluator


@pytest.fixture
def evaluator():
    return ExpressionEvaluator()


# ---- Tests ----


def test_arithmetic_expression(evaluator):
    """input_0 * 365 → numeric result."""
    result = evaluator.evaluate(
        expression="input_0 * 365",
        expression_type="python_expr",
        input_values={"input_0": 1},
    )
    assert result == 365


def test_arithmetic_expression_float(evaluator):
    """input_0 * input_1 → float product."""
    result = evaluator.evaluate(
        expression="input_0 * input_1",
        expression_type="python_expr",
        input_values={"input_0": 2.5, "input_1": 4},
    )
    assert result == 10.0


def test_string_concatenation_expression(evaluator):
    """input_0 + ' ' + input_1 → concatenated string."""
    result = evaluator.evaluate(
        expression="input_0 + ' ' + input_1",
        expression_type="python_expr",
        input_values={"input_0": "hello", "input_1": "world"},
    )
    assert result == "hello world"


def test_identity_expression_passthrough(evaluator):
    """Identity expression returns input_0 unchanged."""
    result = evaluator.evaluate(
        expression="input_0",
        expression_type="identity",
        input_values={"input_0": "subject-42"},
    )
    assert result == "subject-42"


def test_unsafe_import_raises_eval_error(evaluator):
    """Expression containing __import__ should raise EvalError."""
    with pytest.raises(EvalError):
        evaluator.evaluate(
            expression="__import__('os').system('ls')",
            expression_type="python_expr",
            input_values={},
        )


def test_unsafe_exec_raises_eval_error(evaluator):
    """Expression using exec() should raise EvalError."""
    with pytest.raises(EvalError):
        evaluator.evaluate(
            expression="exec('import os')",
            expression_type="python_expr",
            input_values={},
        )


def test_plugin_dispatch(evaluator, monkeypatch):
    """Plugin expression_type='plugin' calls the named function."""
    import src.services.expression_eval as ee_module

    def fake_loader(dotted_path: str):
        return lambda **kwargs: 42

    monkeypatch.setattr(ee_module, "_load_plugin", fake_loader)

    result = evaluator.evaluate(
        expression="some.module.my_func",
        expression_type="plugin",
        input_values={"input_0": "data"},
    )
    assert result == 42


def test_unknown_expression_type_raises_eval_error(evaluator):
    """Unknown expression_type should raise EvalError."""
    with pytest.raises(EvalError, match="expression_type"):
        evaluator.evaluate(
            expression="input_0",
            expression_type="totally_unknown",
            input_values={"input_0": "x"},
        )
