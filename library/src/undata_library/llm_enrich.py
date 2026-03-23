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

# LLM result cache — keyed by (element_desc, term_label, term_defn)
_LLM_CACHE: dict[tuple[str, str, str], str] = {}
_CACHE_PATH: str | None = None


def _get_default_model() -> str:
    """Select default model: OpenAI if key available, else local ollama."""
    model = os.environ.get("UNDATA_LLM_MODEL")
    if model:
        return model
    return "gpt-4.1-nano" if os.environ.get("OPENAI_API_KEY") else "ollama/qwen3.5:latest"


def _load_cache(cache_dir: str | None = None) -> None:
    """Load LLM decision cache from disk."""
    global _LLM_CACHE, _CACHE_PATH
    import json
    from pathlib import Path

    if cache_dir:
        _CACHE_PATH = str(Path(cache_dir) / "llm-cache.json")
    elif _CACHE_PATH is None:
        _CACHE_PATH = str(Path.home() / ".cache" / "undata" / "llm-cache.json")

    try:
        with open(_CACHE_PATH) as f:
            data = json.load(f)
        _LLM_CACHE = {tuple(k.split("|||")): v for k, v in data.items()}
        logger.info("Loaded %d cached LLM decisions from %s", len(_LLM_CACHE), _CACHE_PATH)
    except (FileNotFoundError, json.JSONDecodeError):
        _LLM_CACHE = {}


def _save_cache() -> None:
    """Save LLM decision cache to disk."""
    import json
    from pathlib import Path

    if _CACHE_PATH is None:
        return
    Path(_CACHE_PATH).parent.mkdir(parents=True, exist_ok=True)
    data = {"|||".join(k): v for k, v in _LLM_CACHE.items()}
    with open(_CACHE_PATH, "w") as f:
        json.dump(data, f)


def verify_borderline_match(
    element_desc: str,
    ontology_term_label: str,
    ontology_term_uri: str,
    ontology_name: str,
    embedding_score: float,
    source_context: str | None = None,
    model: str | None = None,
    ontology_term_definition: str | None = None,
    ontology_term_synonyms: list[str] | None = None,
) -> dict:
    """Ask an LLM to verify a borderline ontology match.

    Sends the ontology term's definition and synonyms so the LLM can
    evaluate semantic equivalence without external knowledge.

    Returns a dict with:
        - model: str (model used)
        - decision: "confirm" | "reject" | "uncertain"
        - confidence: float (0.0-1.0)
        - justification: str (LLM's reasoning)
        - error: str | None (if LLM call failed)
    """
    model = model or os.environ.get("UNDATA_LLM_MODEL", "ollama/qwen3.5:latest")

    prompt = _build_verification_prompt(
        element_desc=element_desc,
        ontology_term_label=ontology_term_label,
        ontology_term_uri=ontology_term_uri,
        ontology_name=ontology_name,
        embedding_score=embedding_score,
        source_context=source_context,
        ontology_term_definition=ontology_term_definition,
        ontology_term_synonyms=ontology_term_synonyms,
    )

    # Try ollama direct API first (avoids litellm compatibility issues)
    if model.startswith("ollama/"):
        try:
            return _call_ollama(model.removeprefix("ollama/"), prompt)
        except Exception as exc:
            logger.warning("Ollama call failed: %s", exc)

    # Fall back to litellm
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
    ontology_term_definition: str | None = None,
    ontology_term_synonyms: list[str] | None = None,
) -> str:
    """Build the prompt for LLM ontology match verification.

    Includes the ontology term's definition and synonyms so the LLM
    can evaluate semantic equivalence without external knowledge.
    """
    context_line = f"\nSource context: {source_context}" if source_context else ""
    defn_line = (
        f"\nOntology term definition: {ontology_term_definition}"
        if ontology_term_definition
        else ""
    )
    syn_line = ""
    if ontology_term_synonyms:
        syn_line = f"\nOntology term synonyms: {', '.join(ontology_term_synonyms[:5])}"

    return f"""Does the following ontology term match this data element? Compare their definitions.

Data element: {element_desc}

Candidate ontology term: {ontology_term_label}
URI: {ontology_term_uri}
Ontology: {ontology_name}{defn_line}{syn_line}{context_line}

Respond in EXACTLY this format (3 lines, no extra text):
DECISION: confirm OR reject OR uncertain
CONFIDENCE: 0.0 to 1.0
JUSTIFICATION: one sentence explaining why"""


def verify_batch(
    pairs: list[tuple[str, str, str, str]],
    model: str | None = None,
    batch_size: int = 30,
) -> list[str]:
    """Verify multiple element-term pairs in batched LLM calls.

    Each pair is (element_desc, term_label, term_definition, term_uri).
    Uses a disk cache to avoid re-running calls on repeated pipeline runs.
    Returns a list of decisions: "confirm", "reject", or "uncertain" for each pair.
    """
    model = model or _get_default_model()
    all_decisions: list[str] = []

    # Load cache
    if not _LLM_CACHE:
        _load_cache()

    # Separate cached from uncached
    uncached_indices: list[int] = []
    uncached_pairs: list[tuple] = []
    for i, (elem_desc, term_label, term_defn, term_uri) in enumerate(pairs):
        cache_key = (elem_desc[:200], term_label, (term_defn or "")[:200])
        if cache_key in _LLM_CACHE:
            all_decisions.append(_LLM_CACHE[cache_key])
        else:
            all_decisions.append("__pending__")
            uncached_indices.append(i)
            uncached_pairs.append((elem_desc, term_label, term_defn, term_uri))

    if not uncached_pairs:
        logger.info("All %d pairs found in LLM cache", len(pairs))
        return all_decisions

    logger.info(
        "LLM verification: %d cached, %d to verify",
        len(pairs) - len(uncached_pairs),
        len(uncached_pairs),
    )

    # Process uncached in batches
    batch_decisions: list[str] = []
    for batch_start in range(0, len(uncached_pairs), batch_size):
        batch = uncached_pairs[batch_start : batch_start + batch_size]

        # Build batch prompt
        lines = [
            "For each pair below, decide if the ontology term matches the data element.",
            "Answer ONLY with the pair number and decision (confirm/reject/uncertain), one per line.",
            "",
        ]
        for i, (elem_desc, term_label, term_defn, term_uri) in enumerate(batch, 1):
            lines.append(f'{i}. Element: "{elem_desc}"')
            term_info = f'"{term_label}'
            if term_defn:
                term_info += f": {term_defn[:150]}"
            term_info += '"'
            lines.append(f"   Term: {term_info}")
            lines.append("")

        lines.append("Format: NUMBER: confirm/reject/uncertain")
        prompt = "\n".join(lines)

        try:
            if model.startswith("ollama/"):
                result = _call_ollama(model.removeprefix("ollama/"), prompt, timeout=120)
                raw = result.get("justification", "")
            elif _llm_completion:
                resp = _llm_completion(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=batch_size * 5,
                    temperature=0.0,
                )
                raw = resp.choices[0].message.content.strip()
            else:
                all_decisions.extend(["uncertain"] * len(batch))
                continue

            # Parse batch response
            decisions_batch = _parse_batch_response(raw, len(batch))
            batch_decisions.extend(decisions_batch)
        except Exception as exc:
            logger.warning("Batch LLM verification failed: %s", exc)
            batch_decisions.extend(["uncertain"] * len(batch))

    # Update cache + fill in pending decisions
    for idx, decision in zip(uncached_indices, batch_decisions):
        all_decisions[idx] = decision
        elem_desc, term_label, term_defn, _ = uncached_pairs[uncached_indices.index(idx)]
        cache_key = (elem_desc[:200], term_label, (term_defn or "")[:200])
        _LLM_CACHE[cache_key] = decision

    # Save cache to disk
    _save_cache()

    return all_decisions


def _parse_batch_response(raw: str, expected_count: int) -> list[str]:
    """Parse batch LLM response into list of decisions."""
    decisions = ["uncertain"] * expected_count
    for line in raw.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        # Parse "1: confirm" or "1. confirm" or just "confirm"
        parts = line.replace(".", ":").split(":", 1)
        if len(parts) == 2:
            try:
                idx = int(parts[0].strip()) - 1
                decision = parts[1].strip().lower()
                if decision in ("confirm", "reject", "uncertain"):
                    if 0 <= idx < expected_count:
                        decisions[idx] = decision
            except ValueError:
                continue
    return decisions


def _call_ollama(model_name: str, prompt: str, timeout: int = 60) -> dict:
    """Call ollama API directly with thinking mode disabled."""
    import httpx

    ollama_url = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

    # Use chat API with think=false to disable thinking mode (qwen3.5)
    resp = httpx.post(
        f"{ollama_url}/api/chat",
        json={
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "think": False,
            "options": {"temperature": 0.0, "num_predict": 150},
        },
        timeout=timeout,
    )
    resp.raise_for_status()
    data = resp.json()
    content = data.get("message", {}).get("content", "").strip()
    return _parse_llm_response(content, f"ollama/{model_name}")


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
