# Research: System Hardening

## R1: LLM Chat Backend Wiring

**Decision**: Wire the existing `/api/chat` SSE endpoint to the chat_service.py which already has tool definitions and litellm integration. The endpoint exists but the frontend ChatPanel sends messages to it — need to verify the full loop works.

**Rationale**: The backend chat_service.py and tool definitions (entity_tools, ontology_tools, pipeline_tools, enrichment_tools) are already implemented. The SSE streaming infrastructure exists. The gap is likely configuration (LLM model env var) and testing, not architecture.

**Key implementation**: Ensure `OPENAI_API_KEY` or `OLLAMA_HOST` is configured. The chat_service uses litellm which supports both. For local dev, ollama with qwen3 is the default.

## R2: Evidence-Based Confidence

**Decision**: Every automated proposal (enrichment annotation, LLM suggestion, transform) must include an evidence chain with 3 components:
1. **Similarity score** — cosine similarity between element embedding and ontology term embedding
2. **Link verification** — HTTP HEAD check that the proposed URI resolves (reuse link health checker)
3. **Reasoning text** — structured explanation of why the match was made (template-generated for embedding matches, LLM-generated for LLM proposals)

**Rationale**: Prevents hallucinated confidence. Curators can assess each component independently.

**Data model**: `EvidenceChain` embedded in every proposal and annotation:
```
{
  "similarity_score": 0.85,
  "similarity_method": "cosine_embedding",
  "source_text": "Age of the participant in years",
  "target_term_uri": "http://purl.obolibrary.org/obo/NCIT_C25150",
  "target_term_label": "Age",
  "target_term_definition": "How long something has existed...",
  "uri_verified": true,
  "reasoning": "Element 'age' describes participant age. NCIT:C25150 'Age' is the closest concept match with cosine similarity 0.85 between element description and term label+definition."
}
```

## R3: Name-Based Transform Matching

**Decision**: Use element provenance name + embedding similarity (threshold 0.8) for cross-source transform detection. The matching is upper-triangular (each pair once) and filtered by type compatibility (no array→singleton unless structural_type).

**Algorithm**:
1. Group elements by provenance name (case-insensitive)
2. For each name group with elements from different sources, evaluate type compatibility
3. Additionally, compute embedding similarity between all cross-source element pairs and create transforms for pairs above threshold
4. Many-to-one: extend TransformRecord with `source_elements: list[str]` (list of sha256/URIs)

## R4: NDA Data Dictionary API

**Decision**: Use the NDA API at `https://nda.nih.gov/api/datadictionary/v2/datastructure/{shortName}` to fetch data dictionaries. Each structure has elements with description, type, valueRange, and notes.

**Adapter**: Similar to CSV adapter — map NDA elements to ClassifiedEntity with data_type, description, min/max from valueRange.

## R5: Ontology Admin from Pyoxigraph

**Decision**: The admin page should query the backend, which queries the pyoxigraph ontology store's `list_loaded()` method. Add a GraphQL query `ontologyStoreInfo` that reads from the store (not the DB table).

## R6: Nightly Export + Download Page

**Decision**: Reuse export_service.py from feature 037. Schedule via asyncio background task (same pattern as discovery_service). Serve archives from a static file endpoint.

## R7: HoMBA Loading

**Decision**: The brain-bican repo at `https://github.com/brain-bican/harmonized_ontology_of_mammalian_brain_anatomy_ontology` has OWL releases. The v2026-04-02 release should have RDF/XML format (not OWL Functional Syntax which pyoxigraph can't load). Download from releases page, attempt load; if format incompatible, convert via owlapi or robot CLI.
