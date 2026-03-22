"""Shared utilities for the undata-library.

Common operations used across multiple modules: YAML I/O, filename
sanitization, URI constants. All functions in this module are public.
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

BASE_URI = "https://schema.undata.live"
"""Base URI for all undata registry entities."""


# ---------------------------------------------------------------------------
# YAML I/O
# ---------------------------------------------------------------------------


def safe_load_yaml(path: Path) -> dict | None:
    """Load a YAML file with consistent error handling.

    Returns the parsed dict, or None if the file is missing, malformed,
    or not a mapping.
    """
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return None
        return data
    except (yaml.YAMLError, OSError, UnicodeDecodeError) as exc:
        logger.debug("Failed to load YAML %s: %s", path, exc)
        return None


def write_yaml(path: Path, data: dict) -> None:
    """Write a dict to a YAML file with consistent formatting."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Filename sanitization
# ---------------------------------------------------------------------------


def sanitize_filename(name: str, max_length: int = 60) -> str:
    """Sanitize a string for safe filesystem use.

    Lowercases, replaces slashes/colons/backslashes/spaces with underscores,
    and truncates to max_length.
    """
    safe = name.lower()
    for char in "/", ":", "\\", " ":
        safe = safe.replace(char, "_")
    return safe[:max_length]
