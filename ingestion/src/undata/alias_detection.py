"""AliasDetector — three-phase alias detection: exact name → type gate → embedding."""

from __future__ import annotations

import csv
import io
from itertools import combinations

import httpx

from undata.logging import get_logger
from undata.models import AliasCandidate

logger = get_logger(__name__)

# Token synonym table — normalized tokens that are considered equivalent
SYNONYM_TABLE: dict[str, str] = {
    "subject": "participant",
    "sub": "participant",
    "age": "age",
    "years": "age",
    "session": "visit",
    "ses": "visit",
    "run": "run_index",
    "acquisition": "acq",
    "task": "task",
    "identifier": "id",
    "sex": "biological_sex",
    "gender": "biological_sex",
}

_STRIP_PREFIXES = ("sub_", "participant_", "subject_")


def normalize_name(name: str) -> str:
    """Normalize a field name for alias comparison."""
    n = name.lower()
    for prefix in _STRIP_PREFIXES:
        if n.startswith(prefix):
            n = n[len(prefix) :]
            break
    # Replace synonyms token by token
    tokens = n.split("_")
    tokens = [SYNONYM_TABLE.get(t, t) for t in tokens]
    return "_".join(tokens)


def _types_compatible(a: dict, b: dict) -> bool:
    return a.get("data_type") == b.get("data_type") and a.get("multivalued") == b.get("multivalued")


class AliasDetector:
    def __init__(
        self,
        backend_url: str,
        token: str,
        threshold: float = 0.92,
        dry_run: bool = False,
        source_filter: list[str] | None = None,
    ) -> None:
        self._backend_url = backend_url.rstrip("/")
        self._token = token
        self._threshold = threshold
        self._dry_run = dry_run
        self._source_filter = source_filter

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    async def _fetch_elements(self) -> list[dict]:
        elements: list[dict] = []
        page = 1
        async with httpx.AsyncClient(timeout=30.0) as client:
            while True:
                resp = await client.get(
                    f"{self._backend_url}/elements",
                    params={"page": page, "limit": 500},
                    headers=self._headers(),
                )
                resp.raise_for_status()
                data = resp.json()
                items = data.get("items", [])
                if not items:
                    break
                for item in items:
                    src = item.get("source", {}).get("name", "")
                    if self._source_filter and src not in self._source_filter:
                        continue
                    elements.append(item)
                if len(items) < 500:
                    break
                page += 1
        return elements

    def _detect_exact_aliases(self, elements: list[dict]) -> list[AliasCandidate]:
        """Phase 1: exact name normalization + type gate."""
        by_norm: dict[str, list[dict]] = {}
        for el in elements:
            norm = normalize_name(el.get("name", ""))
            by_norm.setdefault(norm, []).append(el)

        candidates: list[AliasCandidate] = []
        for norm_name, group in by_norm.items():
            if len(group) < 2:
                continue
            for a, b in combinations(group, 2):
                if a.get("id") == b.get("id"):
                    continue
                if not _types_compatible(a, b):
                    continue
                candidates.append(
                    AliasCandidate(
                        element_a_id=a["id"],
                        element_b_id=b["id"],
                        similarity_score=1.0,
                        predicate="skos:exactMatch",
                        detection_method="exact_name",
                    )
                )
        return candidates

    def _detect_embedding_aliases(
        self, elements: list[dict], exact_pairs: set[tuple[str, str]]
    ) -> list[AliasCandidate]:
        """Phase 3: sentence-transformer cosine similarity on descriptions."""
        try:
            from sentence_transformers import SentenceTransformer, util
        except ImportError:
            logger.warning("sentence-transformers not available; skipping embedding phase")
            return []

        if len(elements) < 2:
            return []

        model = SentenceTransformer("all-MiniLM-L6-v2")
        descriptions = [el.get("description", el.get("name", "")) for el in elements]
        embeddings = model.encode(descriptions, convert_to_tensor=True)

        candidates: list[AliasCandidate] = []
        for i, j in combinations(range(len(elements)), 2):
            a, b = elements[i], elements[j]
            pair = (a["id"], b["id"])
            rev_pair = (b["id"], a["id"])
            if pair in exact_pairs or rev_pair in exact_pairs:
                continue
            if not _types_compatible(a, b):
                continue
            score = float(util.cos_sim(embeddings[i], embeddings[j])[0][0])
            if score >= self._threshold:
                predicate = "skos:exactMatch" if score >= 0.92 else "skos:closeMatch"
                candidates.append(
                    AliasCandidate(
                        element_a_id=a["id"],
                        element_b_id=b["id"],
                        similarity_score=score,
                        predicate=predicate,
                        detection_method="embedding",
                    )
                )
        return candidates

    async def _register_mapping(self, client: httpx.AsyncClient, candidate: AliasCandidate) -> None:
        await client.post(
            f"{self._backend_url}/mappings",
            json={
                "function_type": "identity",
                "input_element_ids": [candidate.element_a_id],
                "output_element_id": candidate.element_b_id,
                "predicate": candidate.predicate,
                "similarity_score": candidate.similarity_score,
                "detection_method": candidate.detection_method,
            },
            headers=self._headers(),
        )

    async def detect(self) -> list[AliasCandidate]:
        elements = await self._fetch_elements()
        logger.info("Running alias detection", extra={"elements": len(elements)})

        exact = self._detect_exact_aliases(elements)
        exact_pairs = {(c.element_a_id, c.element_b_id) for c in exact}
        embedding = self._detect_embedding_aliases(elements, exact_pairs)
        all_candidates = exact + embedding

        logger.info(
            "Alias detection complete",
            extra={"exact": len(exact), "embedding": len(embedding)},
        )

        if not self._dry_run and all_candidates:
            async with httpx.AsyncClient(timeout=30.0) as client:
                for candidate in all_candidates:
                    try:
                        await self._register_mapping(client, candidate)
                    except Exception as exc:
                        logger.warning(
                            "Failed to register mapping",
                            extra={
                                "error": str(exc),
                                "pair": (candidate.element_a_id, candidate.element_b_id),
                            },
                        )

        return all_candidates

    def to_sssom_tsv(self, candidates: list[AliasCandidate]) -> str:
        buf = io.StringIO()
        writer = csv.writer(buf, delimiter="\t")
        writer.writerow(
            ["subject_id", "predicate_id", "object_id", "match_type", "similarity_score"]
        )
        for c in candidates:
            writer.writerow(
                [
                    c.element_a_id,
                    c.predicate,
                    c.element_b_id,
                    c.detection_method,
                    round(c.similarity_score, 4),
                ]
            )
        return buf.getvalue()
