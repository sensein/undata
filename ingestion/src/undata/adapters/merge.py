"""Merge utilities for dual-path (code + file) adapter results (US3).

merge_elements(code_elements, file_elements) → list[NormalizedElement]
merge_classes(code_classes, file_classes)   → list[SchemaClassPayload]

Deduplication semantics:
- Matching source_local_id (for elements) or class_name (for classes):
    → extraction_path set to "both"
    → code element wins type conflict unless identical (WARN logged)
    → type mismatch: ERROR logged + IDs suffixed with .code / .file
- Code-only element (no file counterpart): extraction_path="code" (WARN)
- File-only element (no code counterpart): extraction_path="file" (WARN)
"""

from __future__ import annotations

import logging

from undata.models import NormalizedElement, SchemaClassPayload

logger = logging.getLogger(__name__)


def merge_elements(
    code_elements: list[NormalizedElement],
    file_elements: list[NormalizedElement],
    merge_strategy: str = "code",
) -> list[NormalizedElement]:
    """Merge code-path and file-path element lists with dedup / conflict detection.

    merge_strategy: "code" (default) means the code-path element wins on matched types.
    """
    code_map: dict[str, NormalizedElement] = {}
    for el in code_elements:
        if el.source_local_id:
            code_map[el.source_local_id] = el

    file_map: dict[str, NormalizedElement] = {}
    for el in file_elements:
        if el.source_local_id:
            file_map[el.source_local_id] = el

    merged: list[NormalizedElement] = []

    # Elements present in both paths
    for slid, code_el in code_map.items():
        if slid in file_map:
            file_el = file_map[slid]
            if code_el.data_type != file_el.data_type:
                # Type conflict — disambiguate with suffixed IDs
                logger.error(
                    "Type conflict for %s: code=%s file=%s; creating .code/.file entries",
                    slid,
                    code_el.data_type,
                    file_el.data_type,
                )
                from dataclasses import replace

                merged.append(
                    replace(
                        code_el,
                        source_local_id=f"{slid}.code",
                        extraction_path="code",
                    )
                )
                merged.append(
                    replace(
                        file_el,
                        source_local_id=f"{slid}.file",
                        extraction_path="file",
                    )
                )
            else:
                # Matching types — produce "both" element; winner determined by merge_strategy
                from dataclasses import replace

                winner = code_el if merge_strategy == "code" else file_el
                merged.append(replace(winner, extraction_path="both"))
        else:
            # Code-only
            logger.warning("Element only in code path: %s", slid)
            merged.append(code_el)

    # Elements only in file path
    for slid, file_el in file_map.items():
        if slid not in code_map:
            logger.warning("Element only in file path: %s", slid)
            merged.append(file_el)

    # Elements with no source_local_id (ungrouped) — append without dedup
    for el in code_elements:
        if not el.source_local_id:
            merged.append(el)
    for el in file_elements:
        if not el.source_local_id:
            merged.append(el)

    return merged


def merge_classes(
    code_classes: list[SchemaClassPayload],
    file_classes: list[SchemaClassPayload],
) -> list[SchemaClassPayload]:
    """Merge code-path and file-path class lists with dedup by class_name."""
    code_map: dict[str, SchemaClassPayload] = {c.class_name: c for c in code_classes}
    file_map: dict[str, SchemaClassPayload] = {c.class_name: c for c in file_classes}

    merged: list[SchemaClassPayload] = []
    from dataclasses import replace

    for name, code_cls in code_map.items():
        if name in file_map:
            # Merge element_source_local_ids from both paths (deduped)
            combined_ids = list(
                dict.fromkeys(
                    code_cls.element_source_local_ids + file_map[name].element_source_local_ids
                )
            )
            merged.append(
                replace(
                    code_cls,
                    element_source_local_ids=combined_ids,
                    extraction_path="both",
                )
            )
        else:
            logger.warning("Class only in code path: %s", name)
            merged.append(code_cls)

    for name, file_cls in file_map.items():
        if name not in code_map:
            logger.warning("Class only in file path: %s", name)
            merged.append(file_cls)

    return merged
