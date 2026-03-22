"""LLM-assisted verification for borderline ontology matches.

When embedding similarity falls in the borderline range (0.7-0.95),
the LLM evaluates the match using element description, ontology term
definition, and source context to confirm or reject the annotation.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

try:
    from litellm import completion as _llm_completion
except ImportError:
    _llm_completion = None


def verify_borderline_match(
    element_desc: str,
    ontology_term_label: str,
    ontology_term_uri: str,
    ontology_name: str,
    embedding_score: float,
    source_context: str | None = None,
    model: str | None = None,
) -> dict:
    """Ask an LLM to verify a borderline ontology match.

    Returns a dict with:
        - model: str (model used)
        - decision: "confirm" | "reject" | "uncertain"
        - confidence: float (0.0-1.0)
        - justification: str (LLM's reasoning)
        - error: str | None (if LLM call failed)
    """
    model = model or os.environ.get("UNDATA_LLM_MODEL", "anthropic/claude-haiku-4-5-20251001")

    prompt = _build_verification_prompt(
        element_desc=element_desc,
        ontology_term_label=ontology_term_label,
        ontology_term_uri=ontology_term_uri,
        ontology_name=ontology_name,
        embedding_score=embedding_score,
        source_context=source_context,
    )

    if _llm_completion is None:
        logger.warning("litellm not installed; skipping LLM verification")
        return {
            "model": model,
            "decision": "uncertain",
            "confidence": 0.0,
            "justification": "litellm not available",
            "error": "litellm not installed",
        }

    try:
        response = _llm_completion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.0,
        )
        content = response.choices[0].message.content.strip()
        return _parse_llm_response(content, model)
    except Exception as exc:
        logger.warning("LLM verification failed: %s", exc)
        return {
            "model": model,
            "decision": "uncertain",
            "confidence": 0.0,
            "justification": "",
            "error": str(exc)[:200],
        }


def _build_verification_prompt(
    element_desc: str,
    ontology_term_label: str,
    ontology_term_uri: str,
    ontology_name: str,
    embedding_score: float,
    source_context: str | None = None,
) -> str:
    """Build the prompt for LLM ontology match verification."""
    context_line = f"\nSource context: {source_context}" if source_context else ""

    return f"""You are verifying whether an ontology term is a correct match for a neuroscience data element.

Data element: {element_desc}
Candidate ontology term: {ontology_term_label} ({ontology_term_uri})
Ontology: {ontology_name}
Embedding similarity score: {embedding_score:.3f}{context_line}

Does this ontology term correctly describe or relate to this data element?

Respond in exactly this format:
DECISION: confirm OR reject OR uncertain
CONFIDENCE: 0.0 to 1.0
JUSTIFICATION: one sentence explaining why"""


def _parse_llm_response(content: str, model: str) -> dict:
    """Parse structured LLM response into a verification dict."""
    decision = "uncertain"
    confidence = 0.5
    justification = content

    for line in content.split("\n"):
        line = line.strip()
        upper = line.upper()
        if upper.startswith("DECISION:"):
            val = line.split(":", 1)[1].strip().lower()
            if val in ("confirm", "reject", "uncertain"):
                decision = val
        elif upper.startswith("CONFIDENCE:"):
            try:
                confidence = float(line.split(":", 1)[1].strip())
                confidence = max(0.0, min(1.0, confidence))
            except ValueError:
                pass
        elif upper.startswith("JUSTIFICATION:"):
            justification = line.split(":", 1)[1].strip()

    return {
        "model": model,
        "decision": decision,
        "confidence": confidence,
        "justification": justification,
        "error": None,
    }
