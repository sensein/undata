"""Tests for staging directory management (Parquet-only)."""

import time

from undata_library.staging import (
    cleanup_stale_staging,
    count_staged,
    create_staging_dir,
    generate_run_id,
    iter_staged,
    write_staged_batch,
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


def test_write_staged_batch(tmp_path):
    staging = create_staging_dir(tmp_path, "test-run")
    entities = [
        {
            "semantic": {"data_type": "string"},
            "provenance": [{"source": "test", "class": "X", "name": "field1"}],
        },
        {
            "semantic": {"data_type": "integer"},
            "provenance": [{"source": "test", "class": "X", "name": "field2"}],
        },
    ]
    written = write_staged_batch(staging, "elements", entities, source="test")
    assert written == 2


def test_count_staged(tmp_path):
    staging = create_staging_dir(tmp_path, "test-run")
    write_staged_batch(
        staging,
        "elements",
        [{"semantic": {"data_type": "string"}, "provenance": [{"source": "t", "class": "X", "name": "a"}]}],
        source="test",
    )
    assert count_staged(staging, "elements") == 1


def test_iter_staged(tmp_path):
    staging = create_staging_dir(tmp_path, "test-run")
    write_staged_batch(
        staging,
        "elements",
        [{"semantic": {"data_type": "string"}, "provenance": [{"source": "t", "class": "X", "name": "a"}]}],
        source="test",
    )
    entities = list(iter_staged(staging, "elements"))
    assert len(entities) == 1


def test_cleanup_stale_staging(tmp_path):
    import os

    old = create_staging_dir(tmp_path, "old-run")
    old_time = time.time() - (25 * 3600)
    os.utime(old, (old_time, old_time))
    create_staging_dir(tmp_path, "new-run")

    removed = cleanup_stale_staging(tmp_path, max_age_hours=24)
    assert removed == 1
    assert not (tmp_path / ".staging" / "old-run").exists()
    assert (tmp_path / ".staging" / "new-run").exists()
