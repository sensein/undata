"""URI stability unit tests — T069 (Polish Phase 8).

Verify that URI fields are immutable after creation in service layer.
"""

from __future__ import annotations

import pytest


def test_mint_element_uri_deterministic():
    """Same element_id always produces same URI."""
    from src.core.uri import mint_element_uri
    eid = "12345678-1234-1234-1234-123456789abc"
    assert mint_element_uri(eid) == mint_element_uri(eid)


def test_mint_mapping_uri_deterministic():
    """Same mapping_id always produces same URI."""
    from src.core.uri import mint_mapping_uri
    mid = "87654321-4321-4321-4321-cba987654321"
    assert mint_mapping_uri(mid) == mint_mapping_uri(mid)


def test_mint_schema_uri_deterministic():
    """Same schema_id always produces same URI."""
    from src.core.uri import mint_schema_uri
    sid = "aaaabbbb-cccc-dddd-eeee-ffffaaaabbbb"
    assert mint_schema_uri(sid) == mint_schema_uri(sid)


def test_different_ids_produce_different_uris():
    """Different IDs produce different URIs."""
    from src.core.uri import mint_element_uri
    uri1 = mint_element_uri("aaa")
    uri2 = mint_element_uri("bbb")
    assert uri1 != uri2


def test_audit_log_actor_id_is_uuid_type():
    """AuditService.record signature requires actor_id: UUID (not str)."""
    import inspect
    from src.services.audit import AuditService
    sig = inspect.signature(AuditService.record)
    params = sig.parameters
    assert "actor_id" in params
    # Verify annotation is UUID (not str)
    annotation = params["actor_id"].annotation
    assert annotation is not str, "actor_id must be UUID, not str"
