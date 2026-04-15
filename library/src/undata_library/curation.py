"""Curation flag management — write, read, resolve flags for human review."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from .models import CurationFlag, FlagStatus, FlagType
from .utils import safe_load_yaml, write_yaml

if TYPE_CHECKING:
    from .storage.protocol import StorageBackend


def create_flag(
    entity_type: str,
    entity_ref: str,
    flag_type: FlagType,
    context: dict,
    llm_verification: dict | None = None,
) -> CurationFlag:
    """Create a new CurationFlag with a generated ID and timestamp."""
    return CurationFlag(
        id=str(uuid.uuid4()),
        entity_type=entity_type,
        entity_ref=entity_ref,
        flag_type=flag_type,
        context=context,
        llm_verification=llm_verification,
        status=FlagStatus.pending,
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def write_flag(
    output_dir: Path | None,
    flag: CurationFlag,
    *,
    backend: StorageBackend | None = None,
) -> Path | str:
    """Write a CurationFlag. Uses backend if provided, else writes to output_dir."""
    if backend is not None:
        return backend.flags.write_flag(flag)

    flags_dir = output_dir / "curation-flags"
    flags_dir.mkdir(parents=True, exist_ok=True)
    filepath = flags_dir / f"{flag.id}.yaml"
    write_yaml(filepath, flag.model_dump(mode="json", exclude_none=True))
    return filepath


def read_flags(
    output_dir: Path | None,
    status: FlagStatus | None = None,
    flag_type: FlagType | None = None,
    *,
    backend: StorageBackend | None = None,
) -> list[CurationFlag]:
    """Read CurationFlags. Uses backend if provided, else reads from output_dir."""
    if backend is not None:
        return backend.flags.read_flags(status=status, flag_type=flag_type)

    flags_dir = output_dir / "curation-flags"
    if not flags_dir.exists():
        return []

    flags: list[CurationFlag] = []
    for f in sorted(flags_dir.glob("*.yaml")):
        data = safe_load_yaml(f)
        if data is None:
            continue
        try:
            flag = CurationFlag.model_validate(data)
        except Exception:
            continue
        if status is not None and flag.status != status:
            continue
        if flag_type is not None and flag.flag_type != flag_type:
            continue
        flags.append(flag)
    return flags


def resolve_flag(
    output_dir: Path | None,
    flag_id: str,
    action: FlagStatus,
    resolved_by: str,
    note: str | None = None,
    *,
    backend: StorageBackend | None = None,
) -> CurationFlag | None:
    """Resolve a CurationFlag. Uses backend if provided, else uses output_dir."""
    if backend is not None:
        return backend.flags.resolve_flag(flag_id, action, resolved_by, note)

    flags_dir = output_dir / "curation-flags"
    filepath = flags_dir / f"{flag_id}.yaml"
    if not filepath.exists():
        return None

    data = safe_load_yaml(filepath)
    if data is None:
        return None

    try:
        flag = CurationFlag.model_validate(data)
    except Exception:
        return None

    flag.status = action
    flag.resolved_at = datetime.now(timezone.utc).isoformat()
    flag.resolved_by = resolved_by
    flag.resolution_note = note

    write_yaml(filepath, flag.model_dump(mode="json", exclude_none=True))
    return flag


def get_known_sources(source_defs_dir: Path | None = None) -> set[str]:
    """Derive the set of known/authorized source names from source_defs/*.yaml.

    If source_defs_dir is None, uses the bundled source_defs directory.
    """
    if source_defs_dir is None:
        source_defs_dir = Path(__file__).parent / "source_defs"

    if not source_defs_dir.exists():
        return set()

    sources: set[str] = set()
    for f in source_defs_dir.glob("*.yaml"):
        if f.name == "ontologies.yaml":
            continue  # Skip ontology definitions
        data = safe_load_yaml(f)
        if data and isinstance(data.get("name"), str):
            sources.add(data["name"])
        else:
            # Use filename stem as fallback
            sources.add(f.stem)
    return sources
