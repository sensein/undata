# Contract: tutorials/conftest.py

**Module**: `tutorials/conftest.py`
**Consumed by**: all notebooks via `pytest --nbmake`

## Fixtures

```python
# Session-scoped — computed once per pytest run

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
    return os.getenv("API_KEY", "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2")

@pytest.fixture(scope="session")
def api_headers(api_key: str) -> dict[str, str]:
    """Standard auth headers for httpx calls."""
    return {"X-API-Key": api_key}

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
```

## pytest.ini_options

```toml
[tool.pytest.ini_options]
addopts = ["--nbmake", "--nbmake-timeout=60"]
testpaths = ["."]  # run from tutorials/ directory
```

## Invariants

- All fixtures are `scope="session"` — computed once, reused across all notebooks.
- `api_key` default is the seeded dev token; safe for local development only.
- `backend_available` returns `False` (not raises) on connection failure.
- Notebooks use env vars directly (not conftest fixtures) because nbmake kernels
  don't receive pytest fixtures; conftest fixtures are for pytest-native tests only.
