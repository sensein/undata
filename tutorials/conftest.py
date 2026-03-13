"""pytest fixtures and hooks for undata tutorials.

Note: Notebooks read env vars directly (nbmake kernels don't receive pytest fixtures).
These fixtures and hooks are for the pytest/nbmake runner layer:
- Session-scoped fixtures provide service URLs, API key, and availability status.
- `pytest_collection_modifyitems` marks service-dependent notebooks as SKIPPED when
  required services are unreachable, so CI reports SKIPPED not FAILED.
"""

import json
import os
from pathlib import Path

import httpx
import pytest


# ---------------------------------------------------------------------------
# Session-scoped fixtures (for native pytest tests; not passed to notebooks)
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def backend_url() -> str:
    """Base URL of the schema backend service."""
    return os.getenv("BACKEND_URL", "http://localhost:8002")


@pytest.fixture(scope="session")
def migration_url() -> str:
    """Base URL of the migration API service."""
    return os.getenv("MIGRATION_URL", "http://localhost:8004")


@pytest.fixture(scope="session")
def api_key() -> str:
    """API key for authenticating with the backend."""
    return os.getenv(
        "API_KEY",
        "qs005testtoken1234567890abcdef1234567890abcdef1234567890abcdef12",
    )


@pytest.fixture(scope="session")
def api_headers(api_key: str) -> dict[str, str]:
    """Standard auth headers for httpx calls."""
    return {"Authorization": f"Bearer {api_key}"}


@pytest.fixture(scope="session")
def backend_available(backend_url: str) -> bool:
    """True if backend health endpoint responds successfully."""
    try:
        httpx.get(f"{backend_url}/health", timeout=2.0).raise_for_status()
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def migration_available(migration_url: str) -> bool:
    """True if migration-api health endpoint responds successfully."""
    try:
        httpx.get(f"{migration_url}/health", timeout=2.0).raise_for_status()
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Skip hook: marks service-dependent notebooks before execution
# ---------------------------------------------------------------------------


def _check_health(url: str) -> bool:
    try:
        httpx.get(f"{url}/health", timeout=2.0).raise_for_status()
        return True
    except Exception:
        return False


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    """Skip service-dependent notebooks when required services are unreachable.

    Reads ``metadata.undata.services_required`` from each .ipynb file.
    Marks the notebook item with ``pytest.mark.skip`` if any required service
    is unavailable.  This produces SKIPPED (not FAILED) in the test report.
    """
    backend_url = os.getenv("BACKEND_URL", "http://localhost:8002")
    migration_url = os.getenv("MIGRATION_URL", "http://localhost:8004")

    # Check each service at most once per pytest session
    _cache: dict[str, bool] = {}

    def available(service: str) -> bool:
        if service not in _cache:
            if service == "backend":
                _cache[service] = _check_health(backend_url)
            elif service == "migration-api":
                _cache[service] = _check_health(migration_url)
            else:
                _cache[service] = True  # unknown service — don't block
        return _cache[service]

    for item in items:
        # Only handle nbmake notebook items
        if not getattr(item, "nbmake", False):
            continue

        nb_path = Path(str(item.fspath))
        if not nb_path.suffix == ".ipynb":
            continue

        try:
            nb = json.loads(nb_path.read_text())
        except Exception:
            continue  # malformed notebook — let nbmake report the error

        undata_meta = nb.get("metadata", {}).get("undata", {})
        services_required: list[str] = undata_meta.get("services_required", [])

        missing = [svc for svc in services_required if not available(svc)]
        if missing:
            url_map = {"backend": backend_url, "migration-api": migration_url}
            reasons = "; ".join(
                f"{svc} unavailable at {url_map.get(svc, '?')}" for svc in missing
            )
            item.add_marker(pytest.mark.skip(reason=reasons))
