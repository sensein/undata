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
        'Respond with JSON: {"term_uri": "...", "term_label": "...", '
        '"ontology": "...", "mapping_relation": "skos:exactMatch|closeMatch|relatedMatch", '
        '"reasoning": "..."}'
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
        'Respond with JSON: {"unit": "...", "unit_uri": "..."'
        ', "reasoning": "..."}'
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
        proposal = (
            json.loads(content[start:end]) if start >= 0 and end > start else {"reasoning": content}
        )

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
        'Respond with JSON: {"description": "...", "reasoning": "..."}'
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
        proposal = (
            json.loads(content[start:end])
            if start >= 0 and end > start
            else {"description": content}
        )

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


# ---------------------------------------------------------------------------
# T043: Alignment Assessment Skill
# ---------------------------------------------------------------------------


async def assess_alignment(
    session: AsyncSession,
    element_a_sha256: str,
    element_b_sha256: str,
    model: str = "ollama_chat/qwen3:0.6b",
) -> dict:
    """Use LLM to assess whether two elements represent the same or different concepts."""
    from src.db.models import Element

    row_a = (
        await session.execute(
            select(Element).where(Element.sha256.startswith(element_a_sha256)).limit(1)
        )
    ).scalar_one_or_none()
    row_b = (
        await session.execute(
            select(Element).where(Element.sha256.startswith(element_b_sha256)).limit(1)
        )
    ).scalar_one_or_none()

    if not row_a or not row_b:
        return {"error": "One or both elements not found"}

    prov_a = row_a.provenance[0] if row_a.provenance else {}
    prov_b = row_b.provenance[0] if row_b.provenance else {}

    prompt = (
        "Compare these two neuroscience data elements and assess if they represent "
        "the same concept, related concepts, or different concepts.\n\n"
        f"Element A:\n  Name: {prov_a.get('name', '')}\n  Source: {prov_a.get('source', '')}\n"
        f"  Class: {prov_a.get('class', '')}\n  Type: {row_a.data_type}\n"
        f"  Unit: {row_a.unit or 'n/a'}\n"
        f"  Description: {prov_a.get('description', '')[:200]}\n\n"
        f"Element B:\n  Name: {prov_b.get('name', '')}\n  Source: {prov_b.get('source', '')}\n"
        f"  Class: {prov_b.get('class', '')}\n  Type: {row_b.data_type}\n"
        f"  Unit: {row_b.unit or 'n/a'}\n"
        f"  Description: {prov_b.get('description', '')[:200]}\n\n"
        "Respond with JSON: "
        '{"relationship": "exactMatch|closeMatch|relatedMatch|different", "reasoning": "..."}'
    )

    try:
        import litellm

        litellm.drop_params = True
        response = await litellm.acompletion(
            model=model, messages=[{"role": "user", "content": prompt}], temperature=0.1
        )
        content = response.choices[0].message.content or ""
        start = content.find("{")
        end = content.rfind("}") + 1
        result = (
            json.loads(content[start:end]) if start >= 0 and end > start else {"reasoning": content}
        )
        return {
            "element_a": prov_a.get("name", element_a_sha256[:12]),
            "element_b": prov_b.get("name", element_b_sha256[:12]),
            **result,
        }
    except Exception as exc:
        return {"error": str(exc)}


# ---------------------------------------------------------------------------
# T045: Batch Enrichment Orchestrator
# ---------------------------------------------------------------------------


async def batch_enrich_elements(
    session: AsyncSession,
    source: str | None = None,
    unannotated_only: bool = True,
    limit: int = 50,
    model: str = "ollama_chat/qwen3:0.6b",
) -> dict:
    """Batch LLM enrichment for elements. Returns job summary."""
    from sqlalchemy import func
    from sqlalchemy import text as sa_text

    from src.db.models import Element

    stmt = select(Element)
    if source:
        stmt = stmt.where(
            sa_text("provenance @> :src ::jsonb").bindparams(src=f'[{{"source": "{source}"}}]')
        )
    if unannotated_only:
        stmt = stmt.where(func.jsonb_array_length(Element.ontology_annotations) == 0)
    stmt = stmt.limit(limit)

    rows = (await session.execute(stmt)).scalars().all()
    total = len(rows)
    processed = 0
    errors = 0

    for row in rows:
        try:
            await suggest_ontology_annotation(session, row.sha256, model=model)
            processed += 1
        except Exception:
            errors += 1

    await session.flush()
    return {"total_queued": total, "processed": processed, "errors": errors, "status": "completed"}
