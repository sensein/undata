"""Archive utilities for registry export/import.

Compress export directories to .tar.gz and extract archives.
"""

from __future__ import annotations

import logging
import tarfile
from pathlib import Path

logger = logging.getLogger(__name__)


def compress_directory(source_dir: Path, output_path: Path | None = None) -> Path:
    """Compress an export directory to .tar.gz.

    If output_path is not provided, creates {source_dir}.tar.gz alongside it.
    Returns path to the compressed archive.
    """
    if output_path is None:
        output_path = source_dir.parent / f"{source_dir.name}.tar.gz"

    logger.info("Compressing %s → %s", source_dir, output_path)
    with tarfile.open(output_path, "w:gz") as tar:
        tar.add(source_dir, arcname=source_dir.name)

    size_mb = output_path.stat().st_size / (1024 * 1024)
    logger.info("Archive created: %.1f MB", size_mb)
    return output_path


def extract_archive(archive_path: Path, output_dir: Path) -> Path:
    """Extract a .tar.gz archive to output_dir.

    Returns path to the extracted directory (first directory in archive).
    """
    logger.info("Extracting %s → %s", archive_path, output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    with tarfile.open(archive_path, "r:gz") as tar:
        # Security: check for path traversal
        for member in tar.getmembers():
            if member.name.startswith("/") or ".." in member.name:
                raise ValueError(f"Unsafe path in archive: {member.name}")
        tar.extractall(output_dir)

    # Find the extracted directory
    extracted = [d for d in output_dir.iterdir() if d.is_dir()]
    if extracted:
        return extracted[0]
    return output_dir
