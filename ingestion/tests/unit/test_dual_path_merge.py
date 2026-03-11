"""Unit tests for merge_elements() and merge_classes() utilities (T025 / US3).

Tests cover:
- Dedup: same SLID from both paths → single merged element with extraction_path="both"
- Code-only: WARN log emitted; element preserved
- File-only: WARN log emitted; element preserved
- Type conflict: ERROR log emitted + disambiguated IDs (.code / .file suffixes)
"""

from __future__ import annotations

import logging

from undata.adapters.merge import merge_classes, merge_elements
from undata.models import NormalizedElement, SchemaClassPayload


def _el(name: str, slid: str, data_type: str = "string") -> NormalizedElement:
    return NormalizedElement(
        name=name,
        data_type=data_type,
        description="",
        required=False,
        multivalued=False,
        allowed_values=None,
        constraints={},
        source_local_id=slid,
        source_name="TEST",
    )


def _cls(name: str, slids: list[str] | None = None) -> SchemaClassPayload:
    return SchemaClassPayload(
        class_name=name,
        description="",
        element_source_local_ids=slids or [],
    )


class TestMergeElements:
    def test_dedup_same_slid_produces_single_element(self):
        """Matching SLID from code + file → one element with extraction_path='both'."""
        code = [_el("field_a", "Model.field_a")]
        file = [_el("field_a", "Model.field_a")]

        result = merge_elements(code, file)

        assert len(result) == 1
        assert result[0].source_local_id == "Model.field_a"
        assert result[0].extraction_path == "both"

    def test_code_only_element_preserved_with_warning(self, caplog):
        """Element only in code path is kept; WARN logged."""
        code = [_el("code_only", "M.code_only")]
        file: list[NormalizedElement] = []

        with caplog.at_level(logging.WARNING):
            result = merge_elements(code, file)

        assert any("code_only" in r.source_local_id for r in result)
        assert any("code path" in rec.message for rec in caplog.records)

    def test_file_only_element_preserved_with_warning(self, caplog):
        """Element only in file path is kept; WARN logged."""
        code: list[NormalizedElement] = []
        file = [_el("file_only", "M.file_only")]

        with caplog.at_level(logging.WARNING):
            result = merge_elements(code, file)

        assert any("file_only" in r.source_local_id for r in result)
        assert any("file path" in rec.message for rec in caplog.records)

    def test_type_conflict_produces_suffixed_ids_and_error_log(self, caplog):
        """Type mismatch on same SLID → .code / .file IDs; ERROR logged."""
        code = [_el("field", "M.field", data_type="string")]
        file = [_el("field", "M.field", data_type="number")]

        with caplog.at_level(logging.ERROR):
            result = merge_elements(code, file)

        slids = {r.source_local_id for r in result}
        assert "M.field.code" in slids
        assert "M.field.file" in slids
        assert any(
            "Type conflict" in rec.message or "conflict" in rec.message.lower()
            for rec in caplog.records
        )

    def test_total_count_with_overlap(self):
        """Three code + two file where one overlaps → four total (dedup on overlap)."""
        code = [
            _el("a", "M.a"),
            _el("b", "M.b"),
            _el("c", "M.c"),
        ]
        file = [
            _el("b", "M.b"),  # overlap
            _el("d", "M.d"),
        ]

        result = merge_elements(code, file)

        slids = {r.source_local_id for r in result}
        # M.a, M.b (merged), M.c, M.d
        assert len(slids) == 4

    def test_no_source_local_id_elements_appended(self):
        """Elements with empty SLID are not deduplicated, just appended."""
        code = [
            NormalizedElement(
                name="anon",
                data_type="string",
                description="",
                required=False,
                multivalued=False,
                allowed_values=None,
                constraints={},
                source_local_id="",
                source_name="T",
            )
        ]
        file = [
            NormalizedElement(
                name="anon",
                data_type="string",
                description="",
                required=False,
                multivalued=False,
                allowed_values=None,
                constraints={},
                source_local_id="",
                source_name="T",
            )
        ]

        result = merge_elements(code, file)
        assert len(result) == 2


class TestMergeClasses:
    def test_dedup_same_class_name_produces_both(self):
        """Classes with same name from code + file → extraction_path='both'."""
        code = [_cls("MyClass", ["M.a", "M.b"])]
        file = [_cls("MyClass", ["M.b", "M.c"])]

        result = merge_classes(code, file)

        assert len(result) == 1
        cls = result[0]
        assert cls.extraction_path == "both"
        # Combined IDs deduplicated: M.a, M.b, M.c
        assert len(cls.element_source_local_ids) == 3

    def test_code_only_class_preserved_with_warning(self, caplog):
        """Class only in code → preserved; WARN logged."""
        code = [_cls("CodeOnly")]
        file: list[SchemaClassPayload] = []

        with caplog.at_level(logging.WARNING):
            result = merge_classes(code, file)

        assert any(c.class_name == "CodeOnly" for c in result)
        assert any("code path" in rec.message for rec in caplog.records)

    def test_file_only_class_preserved_with_warning(self, caplog):
        """Class only in file → preserved; WARN logged."""
        code: list[SchemaClassPayload] = []
        file = [_cls("FileOnly")]

        with caplog.at_level(logging.WARNING):
            result = merge_classes(code, file)

        assert any(c.class_name == "FileOnly" for c in result)
        assert any("file path" in rec.message for rec in caplog.records)

    def test_total_count_with_overlap(self):
        """Two code + two file where one overlaps → three total."""
        code = [_cls("A"), _cls("B")]
        file = [_cls("B"), _cls("C")]

        result = merge_classes(code, file)

        names = {c.class_name for c in result}
        assert names == {"A", "B", "C"}
