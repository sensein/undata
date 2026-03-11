"""AuthZ edge case unit tests — T068 (Polish Phase 8)."""

from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from src.services.authz import Role, check_role, check_source_access


@pytest.mark.asyncio
async def test_mint_element_uri_format():
    """mint_element_uri produces expected URI format."""
    from src.core.uri import mint_element_uri
    uri = mint_element_uri("abc-123")
    assert uri.endswith("/elements/abc-123")
    assert uri.startswith("http")


@pytest.mark.asyncio
async def test_mint_mapping_uri_format():
    """mint_mapping_uri produces expected URI format."""
    from src.core.uri import mint_mapping_uri
    uri = mint_mapping_uri("def-456")
    assert uri.endswith("/mappings/def-456")


@pytest.mark.asyncio
async def test_mint_schema_uri_format():
    """mint_schema_uri produces expected URI format."""
    from src.core.uri import mint_schema_uri
    uri = mint_schema_uri("ghi-789")
    assert uri.endswith("/schemas/ghi-789")


@pytest.mark.asyncio
async def test_check_role_admin_passes_all():
    """Admin role passes all role checks."""
    import uuid
    from unittest.mock import MagicMock
    session = AsyncMock()
    user = MagicMock()
    user.id = uuid.uuid4()

    with patch("src.services.authz._get_user_global_role", new=AsyncMock(return_value=Role.ADMIN)):
        # Should not raise
        await check_role(session, user, Role.CURATOR)
        await check_role(session, user, Role.CONTRIBUTOR)
        await check_role(session, user, Role.VIEWER)
        await check_role(session, user, Role.ADMIN)


@pytest.mark.asyncio
async def test_check_role_viewer_rejected_for_curator():
    """Viewer cannot pass curator role check."""
    import uuid
    from unittest.mock import MagicMock
    from fastapi import HTTPException
    session = AsyncMock()
    user = MagicMock()
    user.id = uuid.uuid4()

    with patch("src.services.authz._get_user_global_role", new=AsyncMock(return_value=Role.VIEWER)):
        with pytest.raises(HTTPException) as exc_info:
            await check_role(session, user, Role.CURATOR)
        assert exc_info.value.status_code == 403
