"""Tests for source cache manager."""

from unittest.mock import patch

import yaml

from undata_library.acquisition import SourceCache, load_source_def


def test_cache_miss_triggers_clone(tmp_path):
    """Cache miss for git_clone source triggers git clone."""
    cache = SourceCache(cache_dir=tmp_path / "cache")
    sd = load_source_def("nwb")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""
        path = cache.acquire(sd, version="v2.7.0")

    assert "nwb" in str(path)
    assert "v2.7.0" in str(path)
    mock_run.assert_called()  # git clone was invoked


def test_cache_hit_no_download(tmp_path):
    """Cached source returns without download."""
    cache = SourceCache(cache_dir=tmp_path / "cache")
    # Pre-populate cache
    cached = tmp_path / "cache" / "nwb" / "v2.7.0"
    cached.mkdir(parents=True)
    (cached / "source-meta.yaml").write_text(yaml.dump({"repo": "x", "version": "v2.7.0"}))

    with patch("subprocess.run") as mock_run:
        path = cache.acquire(load_source_def("nwb"), version="v2.7.0")

    mock_run.assert_not_called()  # No git clone
    assert path == cached


def test_refresh_forces_redownload(tmp_path):
    """--refresh bypasses cache."""
    cache = SourceCache(cache_dir=tmp_path / "cache")
    cached = tmp_path / "cache" / "nwb" / "v2.7.0"
    cached.mkdir(parents=True)

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""
        cache.acquire(load_source_def("nwb"), version="v2.7.0", refresh=True)

    mock_run.assert_called()  # git clone was invoked despite cache


def test_offline_with_cache_succeeds(tmp_path):
    """--offline with existing cache works."""
    cache = SourceCache(cache_dir=tmp_path / "cache")
    cached = tmp_path / "cache" / "nwb" / "latest"
    cached.mkdir(parents=True)
    (cached / "source-meta.yaml").write_text(yaml.dump({"version": "latest"}))

    path = cache.acquire(load_source_def("nwb"), offline=True)
    assert path == cached


def test_offline_without_cache_raises(tmp_path):
    """--offline without cache raises error."""
    cache = SourceCache(cache_dir=tmp_path / "cache")
    try:
        cache.acquire(load_source_def("nwb"), version="v999", offline=True)
        assert False, "Should have raised"
    except RuntimeError as e:
        assert "not cached" in str(e)
        assert "--offline" in str(e)


def test_source_meta_written(tmp_path):
    """source-meta.yaml written after acquisition."""
    cache = SourceCache(cache_dir=tmp_path / "cache")
    sd = load_source_def("nwb")

    with patch("subprocess.run") as mock_run:
        mock_run.return_value.returncode = 0
        mock_run.return_value.stderr = ""
        path = cache.acquire(sd, version="v2.7.0")

    meta_file = path / "source-meta.yaml"
    assert meta_file.exists()
    meta = yaml.safe_load(meta_file.read_text())
    assert meta["repo"] == sd.repo
    assert meta["version"] == "v2.7.0"
    assert "downloaded_at" in meta


def test_cache_list(tmp_path):
    """cache list shows cached sources."""
    cache = SourceCache(cache_dir=tmp_path / "cache")
    cached = tmp_path / "cache" / "bids" / "v1.9.0"
    cached.mkdir(parents=True)
    (cached / "source-meta.yaml").write_text(
        yaml.dump({"version": "v1.9.0", "downloaded_at": "2026-03-20T00:00:00Z"})
    )
    entries = cache.list_cached()
    assert len(entries) == 1
    assert entries[0]["source"] == "bids"
    assert entries[0]["version"] == "v1.9.0"
