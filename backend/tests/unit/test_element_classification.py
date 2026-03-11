"""Unit tests for element_kind derivation, SchemaEnumeration creation, and DataElementChild depth guard.

TDD: These tests MUST FAIL before the corresponding implementation tasks.
"""

from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# T013 — element_kind derivation logic
# ---------------------------------------------------------------------------


class TestElementKindDerivation:
    """Tests for the derive_element_kind() pure function."""

    def test_enum_from_nonempty_allowed_values(self):
        from src.services.schema_class import derive_element_kind

        assert derive_element_kind(allowed_values=["M", "F", "O"], data_type="string") == "enumeration"

    def test_scalar_from_empty_allowed_values(self):
        from src.services.schema_class import derive_element_kind

        assert derive_element_kind(allowed_values=[], data_type="string") == "scalar"

    def test_scalar_from_none_allowed_values(self):
        from src.services.schema_class import derive_element_kind

        assert derive_element_kind(allowed_values=None, data_type="string") == "scalar"

    def test_complex_from_object_data_type(self):
        from src.services.schema_class import derive_element_kind

        assert derive_element_kind(allowed_values=None, data_type="object") == "complex"

    def test_array_from_array_data_type(self):
        from src.services.schema_class import derive_element_kind

        assert derive_element_kind(allowed_values=None, data_type="array") == "array"

    def test_array_from_multivalued_flag(self):
        from src.services.schema_class import derive_element_kind

        assert derive_element_kind(allowed_values=None, data_type="string", multivalued=True) == "array"

    def test_scalar_default(self):
        from src.services.schema_class import derive_element_kind

        assert derive_element_kind(allowed_values=None, data_type="integer") == "scalar"

    def test_enum_wins_over_object_data_type(self):
        """allowed_values takes precedence over data_type='object'."""
        from src.services.schema_class import derive_element_kind

        assert derive_element_kind(allowed_values=["a", "b"], data_type="object") == "enumeration"

    def test_node_kind_defaults_to_field(self):
        """node_kind is 'field' by default."""
        from src.services.schema_class import DEFAULT_NODE_KIND

        assert DEFAULT_NODE_KIND == "field"


# ---------------------------------------------------------------------------
# T062a — SchemaEnumeration row creation
# ---------------------------------------------------------------------------


class TestSchemaEnumerationCreation:
    """Tests for create_schema_enumerations() — must FAIL before T062b."""

    @pytest.mark.asyncio
    async def test_creates_rows_for_enumeration_element(self, db_session, mock_curator_user):
        """Three SchemaEnumeration rows created for element with 3 allowed_values."""
        from sqlalchemy import select

        from src.models.db import SchemaEnumeration
        from src.services.schema_class import create_schema_enumerations

        # Create a fake element id (not persisted — testing the service call shape)
        import uuid

        element_id = uuid.uuid4()

        # The service should insert rows into schema_enumeration
        # We call it and check the returned objects (DB not required for this pure logic test)
        enums = await create_schema_enumerations(
            element_id=element_id,
            allowed_values=["M", "F", "O"],
            db=db_session,
        )

        assert len(enums) == 3
        values = [e.value for e in enums]
        assert "M" in values
        assert "F" in values
        assert "O" in values
        positions = [e.position for e in enums]
        assert positions == [0, 1, 2]

    @pytest.mark.asyncio
    async def test_no_rows_for_non_enumeration_element(self, db_session, mock_curator_user):
        """No SchemaEnumeration rows for empty allowed_values."""
        import uuid

        from src.services.schema_class import create_schema_enumerations

        element_id = uuid.uuid4()
        enums = await create_schema_enumerations(
            element_id=element_id,
            allowed_values=[],
            db=db_session,
        )
        assert enums == []

    @pytest.mark.asyncio
    async def test_no_rows_for_none_allowed_values(self, db_session, mock_curator_user):
        import uuid

        from src.services.schema_class import create_schema_enumerations

        element_id = uuid.uuid4()
        enums = await create_schema_enumerations(
            element_id=element_id,
            allowed_values=None,
            db=db_session,
        )
        assert enums == []


# ---------------------------------------------------------------------------
# T063a — DataElementChild creation + depth guard
# ---------------------------------------------------------------------------


class TestDataElementChildDepthGuard:
    """Tests for the max nesting depth guard — must FAIL before T063b."""

    def test_depth_guard_raises_at_limit(self):
        """Nesting beyond 10 levels raises ValueError."""
        from src.services.schema_class import check_nesting_depth

        with pytest.raises(ValueError, match="nesting depth"):
            check_nesting_depth(current_depth=10)

    def test_depth_guard_ok_at_max_minus_one(self):
        from src.services.schema_class import check_nesting_depth

        # Should not raise at depth 9 (0-indexed, so 10th level is the limit)
        check_nesting_depth(current_depth=9)

    def test_depth_guard_ok_at_zero(self):
        from src.services.schema_class import check_nesting_depth

        check_nesting_depth(current_depth=0)
