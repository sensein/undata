"""Content-addressed hashing for semantic identity."""

from __future__ import annotations

import hashlib
import json
from typing import Any

BASE_URI = "https://schema.undata.live"
SHORT_KEY_LENGTH = 12  # 12 hex chars = 6 bytes = 2^48 key space (~16.7M collision threshold)


# Fields excluded from identity hash (descriptive metadata, varies by source)
_EXCLUDED_FROM_HASH = {"question_text", "value_domain", "ontology_annotations", "description", "unit_uri"}
# unit_uri is excluded from the hash dict because its value replaces `unit` before hashing

# Deprecated constraint fields (replaced by top-level min_value/max_value)
_DEPRECATED_CONSTRAINT_FIELDS = {"minimum", "maximum"}


def canonical_json(semantic: dict[str, Any]) -> str:
    """Produce a canonical JSON string from a semantic identity dict.

    - Keys sorted alphabetically
    - None/null values omitted
    - question_text and value_domain excluded (not part of identity)
    - constraints.minimum/maximum excluded (use min_value/max_value)
    - response_options sorted by 'value' field for determinism
    - Compact (no whitespace)
    """

    # Normalize unit: if unit_uri exists, use it as the unit value for hashing
    # This ensures "kg" and "kilogram" produce the same hash when both resolve to qudt:KiloGM
    if "unit_uri" in semantic and semantic["unit_uri"]:
        semantic = {**semantic, "unit": semantic["unit_uri"]}

    def _prune(obj: Any, parent_key: str = "") -> Any:
        if isinstance(obj, dict):
            result = {}
            for k, v in sorted(obj.items()):
                if v is None:
                    continue
                if k in _EXCLUDED_FROM_HASH:
                    continue
                if parent_key == "constraints" and k in _DEPRECATED_CONSTRAINT_FIELDS:
                    continue
                pruned_v = _prune(v, parent_key=k)
                if pruned_v is not None:
                    result[k] = pruned_v
            return result if result else None
        if isinstance(obj, list):
            pruned = [_prune(v) for v in obj if v is not None]
            # Sort response_options by 'value' field for determinism
            if parent_key == "response_options" and pruned:
                if isinstance(pruned[0], dict) and "value" in pruned[0]:
                    pruned = sorted(pruned, key=lambda x: x.get("value", ""))
            return pruned if pruned else None
        return obj

    pruned = _prune(semantic)
    if pruned is None:
        pruned = {}
    return json.dumps(pruned, sort_keys=True, separators=(",", ":"))


def compute_sha256(canonical: str) -> str:
    """Compute SHA-256 hex digest of a canonical JSON string."""
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def generate_short_key(sha256_hex: str, **_kwargs) -> str:
    """Generate a deterministic 12-hex-char key from SHA-256.

    Uses the first 12 hex characters (6 bytes) of the SHA-256 digest.
    Key space: 2^48 ≈ 281 trillion — collision threshold ~16.7M elements.
    Fully deterministic: same SHA-256 always produces the same key,
    regardless of which system computes it.
    """
    return sha256_hex[:SHORT_KEY_LENGTH]


def build_element_uri(attribute: str, key: str) -> str:
    """Build a full element URI from attribute name and short key."""
    return f"{BASE_URI}/elements/{attribute.lower()}_{key}"


def build_value_uri(label: str, key: str) -> str:
    """Build a full value concept URI from label and short key."""
    return f"{BASE_URI}/values/{label.lower()}_{key}"


def build_transform_uri(source_name: str, target_name: str, key: str) -> str:
    """Build a full transform URI from source/target names and short key."""
    return f"{BASE_URI}/transforms/{source_name.lower()}_to_{target_name.lower()}_{key}"


def build_valueset_uri(name: str, key: str) -> str:
    """Build a full valueset URI from name and short key."""
    return f"{BASE_URI}/valuesets/{name.lower()}_{key}"


def build_schema_uri(name: str, key: str) -> str:
    """Build a full schema URI from class name and short key."""
    return f"{BASE_URI}/schemas/{name.lower()}_{key}"


def compute_element_hash(semantic_dict: dict[str, Any]) -> tuple[str, str]:
    """Compute SHA-256 and canonical JSON for an element's semantic identity.

    Returns (sha256_hex, canonical_json_str).
    """
    canonical = canonical_json(semantic_dict)
    sha256_hex = compute_sha256(canonical)
    return sha256_hex, canonical


def determine_hash_mode(
    ontology_annotations: list[dict] | None,
) -> tuple[bool, str | None]:
    """Determine whether to use ontology-anchored or structural fallback hash.

    Returns (ontology_anchored: bool, primary_uri: str | None).
    Ontology-anchored when primary annotation has exactMatch or element_match.
    """
    if not ontology_annotations:
        return False, None

    for ann in ontology_annotations:
        if not isinstance(ann, dict):
            continue
        if ann.get("primary"):
            relation = ann.get("mapping_relation", "")
            match_level = ann.get("match_level", "")
            if relation == "skos:exactMatch" or match_level == "element_match":
                return True, ann.get("term_uri")
            return False, None

    # No primary found — check first annotation
    if ontology_annotations and isinstance(ontology_annotations[0], dict):
        ann = ontology_annotations[0]
        relation = ann.get("mapping_relation", "")
        match_level = ann.get("match_level", "")
        if relation == "skos:exactMatch" or match_level == "element_match":
            return True, ann.get("term_uri")

    return False, None


def compute_identity_hash(
    semantic: dict[str, Any],
    provenance: list[dict] | None = None,
    ontology_anchored: bool = False,
    primary_ontology_uri: str | None = None,
) -> tuple[str, str]:
    """Compute post-enrichment identity hash in two modes.

    Ontology-anchored: data_type + unit + pattern + response_options + min/max + type_ref + primary_ontology_uri
    Structural fallback: data_type + unit + pattern + response_options + min/max + type_ref + class + attribute + description

    Returns (sha256_hex, canonical_json_str).
    """
    # Start with the standard canonical (excludes description, ontology_annotations, etc.)
    base = canonical_json(semantic)
    base_dict = json.loads(base) if base else {}

    if ontology_anchored and primary_ontology_uri:
        base_dict["_primary_ontology_uri"] = primary_ontology_uri
    else:
        # Structural fallback: include class + attribute + description from first provenance
        if provenance and len(provenance) > 0:
            first_prov = provenance[0]
            if isinstance(first_prov, dict):
                prov_class = first_prov.get("class", first_prov.get("class_", ""))
                prov_name = first_prov.get("name", "")
                prov_desc = first_prov.get("description", "")
                if prov_class:
                    base_dict["_class"] = prov_class
                if prov_name:
                    base_dict["_attribute"] = prov_name
                if prov_desc:
                    base_dict["_description"] = prov_desc
        # Also include description from semantic block if available
        desc = semantic.get("description")
        if desc and "_description" not in base_dict:
            base_dict["_description"] = desc

    canonical = json.dumps(base_dict, sort_keys=True, separators=(",", ":"))
    sha256_hex = compute_sha256(canonical)
    return sha256_hex, canonical
