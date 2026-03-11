"""Structured JSON logging for the Schema Backend service."""

import logging
import sys

from pythonjsonlogger.json import JsonFormatter

_configured = False


def _configure_root_logger(log_level: str = "INFO") -> None:
    global _configured
    if _configured:
        return

    handler = logging.StreamHandler(sys.stdout)
    formatter = JsonFormatter(
        fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
        rename_fields={
            "asctime": "timestamp",
            "levelname": "level",
            "name": "logger",
        },
        static_fields={"service": "schema-backend"},
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)
    _configured = True


def get_logger(name: str) -> logging.Logger:
    """Return a named logger configured with JSON output.

    The root logger is configured lazily on first call using the
    ``LOG_LEVEL`` setting (or INFO by default). Subsequent calls
    reuse the existing configuration.

    Args:
        name: Logger name (typically ``__name__``).

    Returns:
        A :class:`logging.Logger` instance.
    """
    try:
        from src.core.config import settings

        log_level = settings.log_level
    except Exception:
        log_level = "INFO"

    _configure_root_logger(log_level)
    return logging.getLogger(name)
