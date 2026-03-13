"""Unit tests for RBAC/ReBAC authorization — T021.

Tests call the pure check_role / check_source_access functions directly
so no DB or FastAPI DI machinery is needed.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import HTTPException


def _make_user(role: str) -> MagicMock:
    user = MagicMock()
    user.id = uuid4()
    return user


async def _mock_global_role_lookup(session, user_id, role_name: str):
    """Helper: monkey-patch _get_user_global_role for a given role string."""
    from src.services import authz as authz_mod  # noqa: PLC0415
    from src.services.authz import Role  # noqa: PLC0415

    original = authz_mod._get_user_global_role

    async def fake(s, uid):
        return Role.from_str(role_name)

    authz_mod._get_user_global_role = fake
    return original


class TestCheckRole:
    """Unit tests for check_role."""

    async def test_viewer_blocked_from_curator_action(self):
        """Viewer role is blocked from curator-only action (403)."""
        import src.services.authz as authz_mod
        from src.services.authz import Role, check_role

        mock_session = AsyncMock()
        user = _make_user("viewer")

        original = authz_mod._get_user_global_role

        async def fake(s, uid):
            return Role.VIEWER

        authz_mod._get_user_global_role = fake
        try:
            with pytest.raises(HTTPException) as exc_info:
                await check_role(mock_session, user, Role.CURATOR)
            assert exc_info.value.status_code == 403
        finally:
            authz_mod._get_user_global_role = original

    async def test_curator_allowed_for_curator_action(self):
        """Curator role passes check_role(CURATOR)."""
        import src.services.authz as authz_mod
        from src.services.authz import Role, check_role

        mock_session = AsyncMock()
        user = _make_user("curator")

        original = authz_mod._get_user_global_role

        async def fake(s, uid):
            return Role.CURATOR

        authz_mod._get_user_global_role = fake
        try:
            result = await check_role(mock_session, user, Role.CURATOR)
            assert result is user
        finally:
            authz_mod._get_user_global_role = original

    async def test_admin_allowed_for_curator_action(self):
        """Admin role passes check_role(CURATOR) (admin ≥ curator)."""
        import src.services.authz as authz_mod
        from src.services.authz import Role, check_role

        mock_session = AsyncMock()
        user = _make_user("admin")

        original = authz_mod._get_user_global_role

        async def fake(s, uid):
            return Role.ADMIN

        authz_mod._get_user_global_role = fake
        try:
            result = await check_role(mock_session, user, Role.CURATOR)
            assert result is user
        finally:
            authz_mod._get_user_global_role = original


class TestCheckSourceAccess:
    """Unit tests for check_source_access."""

    async def test_viewer_with_source_owner_membership_allowed(self):
        """Viewer with source 'owner' membership passes for that source."""
        import src.services.authz as authz_mod
        from sqlalchemy import select
        from src.services.authz import Role, check_source_access

        source_id = uuid4()
        user = _make_user("viewer")

        # Mock global role = VIEWER
        original_role = authz_mod._get_user_global_role

        async def fake_role(s, uid):
            return Role.VIEWER

        authz_mod._get_user_global_role = fake_role

        # Mock membership lookup returning an 'owner' membership
        mock_membership = MagicMock()
        mock_membership.source_id = source_id
        mock_membership.role = "owner"

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_membership

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        try:
            result = await check_source_access(mock_session, user, source_id, Role.CONTRIBUTOR)
            assert result is user
        finally:
            authz_mod._get_user_global_role = original_role

    async def test_viewer_without_membership_is_403(self):
        """Viewer without any source membership gets 403."""
        import src.services.authz as authz_mod
        from src.services.authz import Role, check_source_access

        source_id = uuid4()
        user = _make_user("viewer")

        original_role = authz_mod._get_user_global_role

        async def fake_role(s, uid):
            return Role.VIEWER

        authz_mod._get_user_global_role = fake_role

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # no membership

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        try:
            with pytest.raises(HTTPException) as exc_info:
                await check_source_access(mock_session, user, source_id, Role.CONTRIBUTOR)
            assert exc_info.value.status_code == 403
        finally:
            authz_mod._get_user_global_role = original_role

    async def test_admin_bypasses_all_source_checks(self):
        """Admin global role bypasses source membership check."""
        import src.services.authz as authz_mod
        from src.services.authz import Role, check_source_access

        source_id = uuid4()
        user = _make_user("admin")

        original_role = authz_mod._get_user_global_role

        async def fake_role(s, uid):
            return Role.ADMIN

        authz_mod._get_user_global_role = fake_role
        mock_session = AsyncMock()

        try:
            result = await check_source_access(mock_session, user, source_id, Role.CONTRIBUTOR)
            assert result is user
            # session.execute should NOT have been called (admin short-circuits)
            mock_session.execute.assert_not_called()
        finally:
            authz_mod._get_user_global_role = original_role
