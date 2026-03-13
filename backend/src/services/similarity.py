"""SimilarityService — embedding-based alias candidate detection."""

from __future__ import annotations

from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.logging import get_logger
from src.models.db import DataElement, DataElementVersion, SchemaSource
from src.models.schemas import AliasCandidatePair, DataElementSummary

if TYPE_CHECKING:
    pass

logger = get_logger(__name__)

_model = None


def _get_model():
    """Lazy-load SentenceTransformer singleton."""
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer("all-MiniLM-L6-v2")
    return _model


def embed(text_content: str) -> list[float]:
    """Encode text to 384-dim vector."""
    model = _get_model()
    return model.encode(text_content).tolist()


async def _build_element_summary(session: AsyncSession, element: DataElement) -> DataElementSummary:
    """Build a DataElementSummary from a DataElement ORM object."""
    version_result = await session.execute(
        select(DataElementVersion).where(DataElementVersion.id == element.current_version_id)
    )
    version = version_result.scalar_one_or_none()

    source_result = await session.execute(
        select(SchemaSource).where(SchemaSource.id == element.source_id)
    )
    source = source_result.scalar_one_or_none()

    from src.models.schemas import SchemaSourceResponse

    source_resp = None
    if source:
        source_resp = SchemaSourceResponse(
            id=source.id,
            name=source.name,
            format=source.format,
            url=source.url,
            version_tag=source.version_tag,
            content_hash=source.content_hash,
            ingested_at=source.ingested_at,
            is_active=source.is_active,
            metadata=source.metadata_,
            version_num=source.version_num,
        )

    return DataElementSummary(
        id=element.id,
        uri=element.uri,
        name=version.name if version else "",
        data_type=version.data_type if version else "",
        description=version.description if version else None,
        required=version.required if version else False,
        multivalued=version.multivalued if version else False,
        source=source_resp,
        unit=version.unit if version else None,
        superseded_by=None,
        version_num=element.version_num,
    )


class SimilarityService:
    @staticmethod
    async def find_candidates(
        session: AsyncSession,
        element_ids: list[str] | None,
        threshold: float,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[int, list[AliasCandidatePair]]:
        """Find alias candidates using cosine similarity on description embeddings.

        When element_ids is None, scans all active elements.
        When element_ids is provided, restricts to that subset.

        Returns (total, list[AliasCandidatePair]) with semantic_graph_overlap=None.
        The caller (AliasGroupService.detect) is responsible for populating overlap.
        """
        # Load elements for candidate pair generation
        query = select(DataElement).where(
            DataElement.deleted_at.is_(None),
            DataElement.superseded_by.is_(None),
        )
        if element_ids:
            uuids = [UUID(eid) for eid in element_ids]
            query = query.where(DataElement.id.in_(uuids))

        result = await session.execute(query)
        elements = list(result.scalars().all())

        if len(elements) < 2:
            return 0, []

        # Load descriptions for embedding comparison
        pairs: list[tuple[DataElement, DataElement, float]] = []

        # Simple approach: compare all pairs using description_embedding
        # In production this uses pgvector HNSW index; here we fall back to application-layer comparison
        element_versions: dict[UUID, DataElementVersion | None] = {}
        for el in elements:
            ver_result = await session.execute(
                select(DataElementVersion).where(DataElementVersion.id == el.current_version_id)
            )
            element_versions[el.id] = ver_result.scalar_one_or_none()

        # Compare all pairs
        for i in range(len(elements)):
            for j in range(i + 1, len(elements)):
                el_a = elements[i]
                el_b = elements[j]
                ver_a = element_versions[el_a.id]
                ver_b = element_versions[el_b.id]

                if ver_a and ver_b and ver_a.description_embedding and ver_b.description_embedding:
                    # Cosine similarity from stored embeddings
                    try:
                        import numpy as np

                        vec_a = np.array(ver_a.description_embedding, dtype=float)
                        vec_b = np.array(ver_b.description_embedding, dtype=float)
                        norm_a = np.linalg.norm(vec_a)
                        norm_b = np.linalg.norm(vec_b)
                        if norm_a > 0 and norm_b > 0:
                            score = float(np.dot(vec_a, vec_b) / (norm_a * norm_b))
                        else:
                            score = 0.0
                    except Exception:
                        score = 0.0
                else:
                    # Fallback: compare names if no embeddings
                    name_a = ver_a.name if ver_a else ""
                    name_b = ver_b.name if ver_b else ""
                    score = 1.0 if name_a and name_b and name_a.lower() == name_b.lower() else 0.0

                if score >= threshold:
                    pairs.append((el_a, el_b, score))

        # Sort by score descending
        pairs.sort(key=lambda x: x[2], reverse=True)

        total = len(pairs)
        pairs = pairs[offset : offset + limit]

        # Build AliasCandidatePair objects
        result_pairs: list[AliasCandidatePair] = []
        for el_a, el_b, score in pairs:
            summary_a = await _build_element_summary(session, el_a)
            summary_b = await _build_element_summary(session, el_b)
            result_pairs.append(
                AliasCandidatePair(
                    element_a=summary_a,
                    element_b=summary_b,
                    similarity_score=score,
                    suggested_predicate="skos:exactMatch" if score >= 0.9 else "skos:closeMatch",
                    semantic_graph_overlap=None,  # populated by AliasGroupService.detect
                )
            )

        return total, result_pairs
