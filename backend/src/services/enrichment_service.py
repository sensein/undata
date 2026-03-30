"""LLM-powered enrichment service — ontology mapping, unit inference, alignment, descriptions.

Provides 4 enrichment skills that use LLM reasoning to improve entity metadata:
1. suggest_ontology_annotation — search ontology store, propose best match with reasoning
2. suggest_unit — infer unit from name+description+context with justification
3. assess_alignment — compare two elements, assess if same or different concept
4. generate_description — create description from element context
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def suggest_ontology_annotation(
    session: AsyncSession,
    entity_sha256: str,
    model: str = "ollama_chat/qwen3:0.6b",
) -> dict:
    """Use LLM to suggest an ontology annotation for an element."""
    from src.db.models import Element, LLMEnrichmentProposal

    stmt = select(Element).where(Element.sha256.startswith(entity_sha256)).limit(1)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        return {"error": f"Element not found: {entity_sha256}"}

    prov = row.provenance[0] if row.provenance else {}
    element_context = (
        f"Name: {prov.get('name', '')}\n"
        f"Source: {prov.get('source', '')}\n"
        f"Class: {prov.get('class', '')}\n"
        f"Data type: {row.data_type}\n"
        f"Unit: {row.unit or 'unknown'}\n"
        f"Description: {prov.get('description', '') or row.description or ''}"
    )

    prompt = (
        "You are a neuroscience data element annotator. Given the following data element, "
        "suggest the most appropriate ontology term from NCIT, DICOM, NIDM, PATO, or RadLex.\n\n"
        f"Element:\n{element_context}\n\n"
        "Respond with JSON: {\"term_uri\": \"...\", \"term_label\": \"...\", "
        "\"ontology\": \"...\", \"mapping_relation\": \"skos:exactMatch|closeMatch|relatedMatch\", "
        "\"reasoning\": \"...\"}"
    )

    try:
        import litellm

        litellm.drop_params = True
        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        content = response.choices[0].message.content or ""

        # Parse JSON from response
        try:
            # Try to extract JSON from the response
            start = content.find("{")
            end = content.rfind("}") + 1
            if start >= 0 and end > start:
                proposal = json.loads(content[start:end])
            else:
                proposal = {"reasoning": content}
        except json.JSONDecodeError:
            proposal = {"reasoning": content}

        # Store proposal
        db_proposal = LLMEnrichmentProposal(
            id=uuid.uuid4(),
            entity_type="element",
            entity_ref=row.sha256,
            proposal_type="ontology_annotation",
            proposed_value=proposal,
            reasoning=proposal.get("reasoning", ""),
            confidence=0.7,
            status="pending",
        )
        session.add(db_proposal)
        await session.flush()

        return {
            "proposal_id": str(db_proposal.id),
            "proposed": proposal,
            "element": prov.get("name", row.sha256[:12]),
        }

    except Exception as exc:
        logger.warning("LLM enrichment failed for %s: %s", entity_sha256, exc)
        return {"error": str(exc)}


async def suggest_unit(
    session: AsyncSession,
    entity_sha256: str,
    model: str = "ollama_chat/qwen3:0.6b",
) -> dict:
    """Use LLM to suggest a unit for an element."""
    from src.db.models import Element, LLMEnrichmentProposal

    stmt = select(Element).where(Element.sha256.startswith(entity_sha256)).limit(1)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        return {"error": f"Element not found: {entity_sha256}"}

    prov = row.provenance[0] if row.provenance else {}
    prompt = (
        f"What unit of measurement does this data element use?\n"
        f"Name: {prov.get('name', '')}\n"
        f"Description: {prov.get('description', '') or row.description or ''}\n"
        f"Data type: {row.data_type}\n"
        f"Current unit: {row.unit or 'not set'}\n\n"
        "Respond with JSON: {\"unit\": \"...\", \"unit_uri\": \"QUDT URI or null\", \"reasoning\": \"...\"}"
    )

    try:
        import litellm

        litellm.drop_params = True
        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
        )
        content = response.choices[0].message.content or ""
        start = content.find("{")
        end = content.rfind("}") + 1
        proposal = json.loads(content[start:end]) if start >= 0 and end > start else {"reasoning": content}

        db_proposal = LLMEnrichmentProposal(
            id=uuid.uuid4(),
            entity_type="element",
            entity_ref=row.sha256,
            proposal_type="unit_correction",
            proposed_value=proposal,
            reasoning=proposal.get("reasoning", ""),
            confidence=0.6,
            status="pending",
        )
        session.add(db_proposal)
        await session.flush()

        return {"proposal_id": str(db_proposal.id), "proposed": proposal}
    except Exception as exc:
        return {"error": str(exc)}


async def generate_description(
    session: AsyncSession,
    entity_sha256: str,
    model: str = "ollama_chat/qwen3:0.6b",
) -> dict:
    """Use LLM to generate a description for an element."""
    from src.db.models import Element, LLMEnrichmentProposal

    stmt = select(Element).where(Element.sha256.startswith(entity_sha256)).limit(1)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if not row:
        return {"error": f"Element not found: {entity_sha256}"}

    prov = row.provenance[0] if row.provenance else {}
    prompt = (
        f"Write a concise description (1-2 sentences) for this neuroscience data element:\n"
        f"Name: {prov.get('name', '')}\n"
        f"Source: {prov.get('source', '')}\n"
        f"Class: {prov.get('class', '')}\n"
        f"Data type: {row.data_type}\n"
        f"Unit: {row.unit or 'not set'}\n\n"
        "Respond with JSON: {\"description\": \"...\", \"reasoning\": \"...\"}"
    )

    try:
        import litellm

        litellm.drop_params = True
        response = await litellm.acompletion(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
        )
        content = response.choices[0].message.content or ""
        start = content.find("{")
        end = content.rfind("}") + 1
        proposal = json.loads(content[start:end]) if start >= 0 and end > start else {"description": content}

        db_proposal = LLMEnrichmentProposal(
            id=uuid.uuid4(),
            entity_type="element",
            entity_ref=row.sha256,
            proposal_type="description",
            proposed_value=proposal,
            reasoning=proposal.get("reasoning", ""),
            confidence=0.8,
            status="pending",
        )
        session.add(db_proposal)
        await session.flush()

        return {"proposal_id": str(db_proposal.id), "proposed": proposal}
    except Exception as exc:
        return {"error": str(exc)}
