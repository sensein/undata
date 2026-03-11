import logging
import sys

from pythonjsonlogger.json import JsonFormatter


def get_logger(name: str) -> logging.Logger:
    """Return a logger that emits JSON-formatted records to stderr."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonFormatter("%(asctime)s %(name)s %(levelname)s %(message)s"))
        logger.addHandler(handler)
        logger.propagate = False
    return logger
