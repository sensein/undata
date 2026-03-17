"""Content-addressed hashing for semantic identity."""

from __future__ import annotations

import hashlib
import json
from typing import Any

BASE_URI = "https://schema.undata.live"
SHORT_KEY_LENGTH = 6
MAX_KEY_LENGTH = 10
BASE36_CHARS = "0123456789abcdefghijklmnopqrstuvwxyz"


def canonical_json(semantic: dict[str, Any]) -> str:
    """Produce a canonical JSON string from a semantic identity dict.

    - Keys sorted alphabetically
    - None/null values omitted
    - Nested dicts also sorted and pruned
    - Compact (no whitespace)
    """

    def _prune(obj: Any) -> Any:
        if isinstance(obj, dict):
            return {k: _prune(v) for k, v in sorted(obj.items()) if v is not None}
        if isinstance(obj, list):
            return [_prune(v) for v in obj if v is not None]
        return obj

    pruned = _prune(semantic)
    return json.dumps(pruned, sort_keys=True, separators=(",", ":"))


def compute_sha256(canonical: str) -> str:
    """Compute SHA-256 hex digest of a canonical JSON string."""
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _bytes_to_base36(data: bytes) -> str:
    """Convert bytes to base36 string."""
    num = int.from_bytes(data, "big")
    if num == 0:
        return "0"
    result = []
    while num:
        num, remainder = divmod(num, 36)
        result.append(BASE36_CHARS[remainder])
    return "".join(reversed(result))


def generate_short_key(
    sha256_hex: str,
    existing_keys: set[str] | None = None,
) -> str:
    """Generate a 6-char base36 key from SHA-256, with collision detection.

    If the generated key collides with an existing key (for a different hash),
    extend by 1 char until unique, up to MAX_KEY_LENGTH.
    """
    raw_bytes = bytes.fromhex(sha256_hex[:8])  # first 4 bytes
    base36 = _bytes_to_base36(raw_bytes)

    # Pad or truncate to SHORT_KEY_LENGTH
    key = base36[:SHORT_KEY_LENGTH].ljust(SHORT_KEY_LENGTH, "0")

    if existing_keys is None:
        return key

    # Collision resolution: extend key length
    length = SHORT_KEY_LENGTH
    full_base36 = _bytes_to_base36(bytes.fromhex(sha256_hex[:16]))
    while key in existing_keys and length < MAX_KEY_LENGTH:
        length += 1
        key = full_base36[:length].ljust(length, "0")

    return key


def build_element_uri(attribute: str, key: str) -> str:
    """Build a full element URI from attribute name and short key."""
    return f"{BASE_URI}/elements/{attribute}_{key}"


def build_value_uri(label: str, key: str) -> str:
    """Build a full value concept URI from label and short key."""
    return f"{BASE_URI}/values/{label}_{key}"


def build_schema_uri(name: str, key: str) -> str:
    """Build a full schema URI from class name and short key."""
    return f"{BASE_URI}/schemas/{name}_{key}"


def compute_element_hash(semantic_dict: dict[str, Any]) -> tuple[str, str]:
    """Compute SHA-256 and canonical JSON for an element's semantic identity.

    Returns (sha256_hex, canonical_json_str).
    """
    canonical = canonical_json(semantic_dict)
    sha256_hex = compute_sha256(canonical)
    return sha256_hex, canonical
