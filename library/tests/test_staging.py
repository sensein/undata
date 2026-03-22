"""Tests for staging directory management."""

import time

from undata_library.staging import (
    cleanup_stale_staging,
    create_staging_dir,
    generate_run_id,
    write_staged_entity,
)


def test_generate_run_id():
    rid = generate_run_id()
    assert len(rid) == 12
    assert rid.replace("-", "").isalnum()


def test_create_staging_dir(tmp_path):
    rid = generate_run_id()
    staging = create_staging_dir(tmp_path, rid)
    assert staging.exists()
    assert (staging / "elements").exists()
    assert (staging / "schemas").exists()
    assert (staging / "values").exists()
    assert (staging / "valuesets").exists()


def test_write_staged_entity(tmp_path):
    staging = create_staging_dir(tmp_path, "test-run")
    data = {
        "semantic": {"data_type": "string"},
        "provenance": [{"source": "test", "class": "X", "name": "field"}],
    }
    path = write_staged_entity(staging, "elements", data)
    assert path.exists()
    assert path.parent.name == "elements"
    assert path.suffix == ".yaml"
    # UUID filename (not content-addressed)
    assert len(path.stem) == 36  # UUID length


def test_cleanup_stale_staging(tmp_path):
    # Create an "old" staging dir
    old = create_staging_dir(tmp_path, "old-run")
    # Backdate its mtime
    import os

    old_time = time.time() - (25 * 3600)  # 25 hours ago
    os.utime(old, (old_time, old_time))

    # Create a "new" staging dir
    create_staging_dir(tmp_path, "new-run")

    removed = cleanup_stale_staging(tmp_path, max_age_hours=24)
    assert removed == 1
    assert not (tmp_path / ".staging" / "old-run").exists()
    assert (tmp_path / ".staging" / "new-run").exists()
