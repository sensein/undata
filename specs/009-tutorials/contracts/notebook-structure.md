# Contract: Notebook Structure

**Applies to**: all `tutorials/*.ipynb` files

## Required Cell Layout

Every tutorial notebook MUST follow this cell ordering:

| Cell | Type | Required Content |
|------|------|-----------------|
| 1 | Markdown | `# TXX: Title` + goal paragraph + "Services required:" list + "Est. time: N min" |
| 2 | Code | Imports + env var reads + service skip check (omit in T06) |
| 3 | Markdown | `## Setup` section heading |
| 4..N-1 | Code + Markdown | Tutorial steps (alternating prose and code) |
| N | Code | Cleanup (delete created resources) — omit for read-only or offline tutorials |
| N+1 | Markdown | `## Next Steps` pointing to the next tutorial |

## Service Skip Cell Template

```python
# Cell 2 — service availability check (REQUIRED in service-dependent notebooks)
import os
import httpx

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8002")
API_KEY = os.getenv(
    "API_KEY",
    "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
)
HEADERS = {"X-API-Key": API_KEY}

try:
    httpx.get(f"{BACKEND_URL}/health", timeout=2.0).raise_for_status()
    print(f"✓ Backend available at {BACKEND_URL}")
except Exception as _e:
    import pytest
    pytest.skip(f"Backend unavailable: {_e}")
```

## Notebook Metadata Requirements

```json
{
  "metadata": {
    "kernelspec": {
      "display_name": "Python 3",
      "language": "python",
      "name": "python3"
    },
    "undata": {
      "tutorial_id": "TXX",
      "services_required": ["backend"],
      "offline": false
    }
  }
}
```

## Code Style Rules

- All Python code in cells MUST pass `ruff check` (line length ≤ 100)
- No `!pip install` or `!uv pip install` in cells (all deps declared in `pyproject.toml`)
- Use `httpx.Client` (synchronous) for HTTP calls — notebooks are not async by default
- Print expected values after each API call: `print(f"Created element: {element['id']}")`
- Assert key properties: `assert response.status_code == 200`

## Cleanup Cell Template

```python
# Cleanup: remove resources created by this tutorial
# (soft-delete is sufficient — elements remain in history)
for resource_id in _created_ids:
    r = httpx.delete(f"{BACKEND_URL}/api/v1/elements/{resource_id}", headers=HEADERS)
    print(f"Deleted {resource_id}: {r.status_code}")

print("✓ Cleanup complete")
```
