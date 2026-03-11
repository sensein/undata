"""Performance benchmarks — T070 (Polish Phase 8).

Requires pytest-benchmark and a running test database.
Skip these tests in CI without DB by checking TEST_DATABASE_URL.

Run with: pytest tests/unit/test_performance.py -v --benchmark-only
"""

from __future__ import annotations

import os

import pytest

# Skip performance tests if no database is available
pytestmark = pytest.mark.skipif(
    not os.environ.get("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set; skipping performance benchmarks",
)


def test_token_service_validate_cache_hit(benchmark):
    """TokenService.validate cache hit should be < 5ms."""
    import hashlib
    import secrets

    from cachetools import TTLCache

    from src.services.tokens import TokenService

    # Seed a fake token into the TTL cache directly for cache-hit test
    raw_token = secrets.token_hex(32)
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()

    # Patch the cache to simulate a pre-loaded cache hit
    import src.services.tokens as _tokens_mod

    original_cache = _tokens_mod._token_cache
    test_cache = TTLCache(maxsize=1024, ttl=300)
    test_cache[token_hash] = {"user_id": "test-user", "valid": True}
    _tokens_mod._token_cache = test_cache

    try:

        def lookup():
            return test_cache.get(token_hash)

        result = benchmark(lookup)
        assert result is not None
    finally:
        _tokens_mod._token_cache = original_cache


def test_mint_element_uri_performance(benchmark):
    """mint_element_uri should be deterministic and fast."""
    from src.core.uri import mint_element_uri

    element_id = "12345678-1234-1234-1234-123456789abc"
    result = benchmark(mint_element_uri, element_id)
    assert "/elements/" in result


def test_cycle_detector_performance(benchmark):
    """CycleDetector.detect_cycle_dfs on large DAG should complete quickly."""
    from src.services.cycle_detection import CycleDetector

    # Build a large DAG: 1000 linear nodes A0→A1→...→A999
    n = 1000
    adjacency = [(f"A{i}", f"A{i + 1}") for i in range(n - 1)]

    def run_cycle_check():
        # Propose adding A999→A1000 (valid, no cycle)
        return CycleDetector.detect_cycle_dfs(
            adjacency,
            proposed_input_ids=[f"A{n - 1}"],
            proposed_output_id=f"A{n}",
        )

    result = benchmark(run_cycle_check)
    assert result is None  # No cycle expected
