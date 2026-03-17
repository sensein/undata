"""Service for content-addressed element operations (v2 model)."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from undata_library.hashing import (
    build_element_uri,
    canonical_json,
    compute_sha256,
    generate_short_key,
)

from ..models.element import ElementProvenance, Element


class ElementService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_or_merge(
        self,
        semantic: dict,
        provenance: list[dict],
    ) -> tuple[Element, bool]:
        """Create a new element or merge provenance into an existing one.

        Returns (element, created) where created=True if new, False if merged.
        """
        # Compute content hash
        sem_dict = dict(semantic)
        if "data_type" in sem_dict:
            sem_dict["data_type"] = str(sem_dict["data_type"])
        canonical = canonical_json(sem_dict)
        sha = compute_sha256(canonical)

        # Check if element exists
        stmt = select(Element).where(Element.semantic_hash == sha)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing:
            # Merge provenance
            existing_keys = {
                (p.source, p.name) for p in existing.provenance
            }
            for prov in provenance:
                if (prov["source"], prov["name"]) not in existing_keys:
                    existing.provenance.append(
                        ElementProvenance(
                            source=prov["source"],
                            class_=prov.get("class", ""),
                            name=prov["name"],
                            description=prov.get("description"),
                            required=prov.get("required"),
                            multivalued=prov.get("multivalued"),
                        )
                    )
            await self.session.flush()
            return existing, False

        # Generate URI
        attr_name = provenance[0]["name"] if provenance else "unknown"

        # Get existing keys for collision detection
        existing_keys_stmt = select(Element.uri)
        existing_result = await self.session.execute(existing_keys_stmt)
        existing_short_keys = set()
        for (uri,) in existing_result:
            parts = uri.rsplit("_", 1)
            if len(parts) == 2:
                existing_short_keys.add(parts[1])

        key = generate_short_key(sha, existing_short_keys)
        uri = build_element_uri(attr_name, key)

        # Create element
        element = Element(
            semantic_hash=sha,
            uri=uri,
            semantic=semantic,
        )
        for prov in provenance:
            element.provenance.append(
                ElementProvenance(
                    source=prov["source"],
                    class_=prov.get("class", ""),
                    name=prov["name"],
                    description=prov.get("description"),
                    required=prov.get("required"),
                    multivalued=prov.get("multivalued"),
                )
            )

        self.session.add(element)
        await self.session.flush()
        return element, True

    async def get_by_uri(self, uri: str) -> Element | None:
        stmt = select(Element).where(Element.uri == uri)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_hash(self, semantic_hash: str) -> Element | None:
        stmt = select(Element).where(Element.semantic_hash == semantic_hash)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_elements(
        self,
        source: str | None = None,
        data_type: str | None = None,
        ontology_term: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[Element], int]:
        """List elements with optional filters. Returns (elements, total_count)."""
        from sqlalchemy import func

        stmt = select(Element)
        count_stmt = select(func.count(Element.id))

        if source:
            stmt = stmt.join(ElementProvenance).where(
                ElementProvenance.source == source
            )
            count_stmt = count_stmt.join(ElementProvenance).where(
                ElementProvenance.source == source
            )

        if data_type:
            stmt = stmt.where(Element.semantic["data_type"].astext == data_type)
            count_stmt = count_stmt.where(
                Element.semantic["data_type"].astext == data_type
            )

        if ontology_term:
            stmt = stmt.where(
                Element.semantic["ontology_term"].astext == ontology_term
            )
            count_stmt = count_stmt.where(
                Element.semantic["ontology_term"].astext == ontology_term
            )

        total = (await self.session.execute(count_stmt)).scalar() or 0
        stmt = stmt.order_by(Element.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total
