"""Expression evaluator: Tier 1 (simpleeval) + Tier 2 (plugin)."""

from __future__ import annotations

import importlib
import logging

from simpleeval import EvalWithCompoundTypes, InvalidExpression

logger = logging.getLogger(__name__)

_UNSAFE_NAMES = frozenset(["__import__", "exec", "eval", "open", "compile", "globals", "locals"])


class EvalError(Exception):
    """Raised when expression evaluation fails or is deemed unsafe."""


def _load_plugin(dotted_path: str):
    """Load a callable by dotted module.function path."""
    parts = dotted_path.rsplit(".", 1)
    if len(parts) != 2:
        raise EvalError(f"Invalid plugin path: {dotted_path!r} (expected 'module.function')")
    module_path, func_name = parts
    try:
        module = importlib.import_module(module_path)
        return getattr(module, func_name)
    except (ImportError, AttributeError) as exc:
        raise EvalError(f"Cannot load plugin {dotted_path!r}: {exc}") from exc


class ExpressionEvaluator:
    """Evaluate mapping expressions safely.

    Tier 1 — expression_type == "python_expr" or "identity":
        Uses simpleeval with an allowlist of names (input_0, input_1, ...).
        Blocks __import__, exec, eval, and other dangerous builtins.

    Tier 2 — expression_type == "plugin":
        Loads a user-supplied Python callable by dotted path via importlib.
        The callable receives keyword arguments for each input (input_0=..., input_1=...).
    """

    def evaluate(
        self,
        expression: str,
        expression_type: str,
        input_values: dict,
    ):
        """Evaluate an expression with the given input values.

        Args:
            expression: The expression string or dotted plugin path.
            expression_type: One of "identity", "python_expr", "plugin".
            input_values: Mapping of variable names (input_0, ...) to values.

        Returns:
            The computed output value.

        Raises:
            EvalError: If the expression is unsafe or evaluation fails.
        """
        if expression_type == "identity":
            return self._eval_simpleeval(expression, input_values)

        if expression_type == "python_expr":
            return self._eval_simpleeval(expression, input_values)

        if expression_type == "plugin":
            return self._eval_plugin(expression, input_values)

        raise EvalError(f"Unknown expression_type: {expression_type!r}")

    def _eval_simpleeval(self, expression: str, names: dict):
        # Pre-check for obviously unsafe patterns
        for unsafe in _UNSAFE_NAMES:
            if unsafe in expression:
                raise EvalError(f"Unsafe expression: contains forbidden name {unsafe!r}")

        evaluator = EvalWithCompoundTypes(names=names)
        # Block dangerous builtins
        evaluator.functions = {}  # no built-in functions allowed
        try:
            return evaluator.eval(expression)
        except InvalidExpression as exc:
            raise EvalError(f"Expression evaluation failed: {exc}") from exc
        except Exception as exc:
            raise EvalError(f"Expression error: {exc}") from exc

    def _eval_plugin(self, dotted_path: str, input_values: dict):
        func = _load_plugin(dotted_path)
        try:
            return func(**input_values)
        except Exception as exc:
            raise EvalError(f"Plugin {dotted_path!r} raised: {exc}") from exc
