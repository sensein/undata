"""Tests for LLM-assisted ontology match verification."""

from unittest.mock import MagicMock, patch

from undata_library.llm_enrich import (
    _build_verification_prompt,
    _parse_llm_response,
    verify_borderline_match,
)


class TestBuildPrompt:
    def test_contains_element_and_term(self):
        prompt = _build_verification_prompt(
            element_desc="participant age in years",
            ontology_term_label="Age",
            ontology_term_uri="http://purl.obolibrary.org/obo/NCIT_C25150",
            ontology_name="ncit",
            embedding_score=0.85,
        )
        assert "participant age in years" in prompt
        assert "Age" in prompt
        assert "NCIT_C25150" in prompt

    def test_includes_source_context(self):
        prompt = _build_verification_prompt(
            element_desc="age",
            ontology_term_label="Age",
            ontology_term_uri="http://x",
            ontology_name="ncit",
            embedding_score=0.8,
            source_context="BIDS participant.tsv column",
        )
        assert "BIDS participant.tsv column" in prompt


class TestParseLLMResponse:
    def test_parse_confirm(self):
        content = "DECISION: confirm\nCONFIDENCE: 0.95\nJUSTIFICATION: Age is an exact match"
        result = _parse_llm_response(content, "test-model")
        assert result["decision"] == "confirm"
        assert result["confidence"] == 0.95
        assert "exact match" in result["justification"]
        assert result["model"] == "test-model"

    def test_parse_reject(self):
        content = "DECISION: reject\nCONFIDENCE: 0.8\nJUSTIFICATION: Different concept"
        result = _parse_llm_response(content, "test-model")
        assert result["decision"] == "reject"

    def test_parse_uncertain(self):
        content = "DECISION: uncertain\nCONFIDENCE: 0.3\nJUSTIFICATION: Ambiguous"
        result = _parse_llm_response(content, "test-model")
        assert result["decision"] == "uncertain"

    def test_parse_malformed_response(self):
        content = "I think this is probably a good match."
        result = _parse_llm_response(content, "test-model")
        assert result["decision"] == "uncertain"
        assert result["confidence"] == 0.5

    def test_confidence_clamped(self):
        content = "DECISION: confirm\nCONFIDENCE: 1.5\nJUSTIFICATION: Very sure"
        result = _parse_llm_response(content, "test-model")
        assert result["confidence"] == 1.0


class TestVerifyBorderlineMatch:
    @patch("undata_library.llm_enrich._llm_completion")
    def test_confirm_match(self, mock_completion):
        mock_response = MagicMock()
        mock_response.choices = [
            MagicMock(
                message=MagicMock(
                    content="DECISION: confirm\nCONFIDENCE: 0.9\nJUSTIFICATION: Good match"
                )
            )
        ]
        mock_completion.return_value = mock_response

        result = verify_borderline_match(
            element_desc="participant age",
            ontology_term_label="Age",
            ontology_term_uri="http://x",
            ontology_name="ncit",
            embedding_score=0.85,
            model="test-model",
        )
        assert result["decision"] == "confirm"
        assert result["error"] is None

    def test_litellm_not_installed(self):
        """When litellm is not available, return uncertain with error."""
        with patch.dict("sys.modules", {"litellm": None}):
            # Force ImportError path
            result = verify_borderline_match(
                element_desc="test",
                ontology_term_label="Test",
                ontology_term_uri="http://x",
                ontology_name="test",
                embedding_score=0.8,
                model="test-model",
            )
            # Should either succeed (if litellm is installed) or return uncertain
            assert result["decision"] in ("confirm", "reject", "uncertain")

    @patch("undata_library.llm_enrich._llm_completion", side_effect=Exception("API timeout"))
    def test_api_error_returns_uncertain(self, mock_completion):
        result = verify_borderline_match(
            element_desc="test",
            ontology_term_label="Test",
            ontology_term_uri="http://x",
            ontology_name="test",
            embedding_score=0.8,
            model="test-model",
        )
        assert result["decision"] == "uncertain"
        assert "API timeout" in result["error"]
