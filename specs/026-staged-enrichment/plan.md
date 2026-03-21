# Implementation Plan: Staged Enrichment Pipeline

**Branch**: `026-staged-enrichment` | **Date**: 2026-03-21 (revised) | **Spec**: spec.md
**Examples**: examples.md (identity model walkthrough + consistency review)

## Summary

Fundamental refactor of the identity model and pipeline flow:
1. Remove `ontology_term` field entirely
2. Post-enrichment hashing (two modes: ontology-anchored vs structural fallback)
3. Staged pipeline: extract (UUIDs) → enrich (in-place) → commit (hash + merge)
4. Unify provenance model across all 4 registry entity types
5. Add missing fields for consistency (description, ontology_annotations on all types)
6. Remove legacy Constraints model
7. Re-extract + evaluate

## Technical Context

**Breaking changes**: Identity hash model completely changed. All existing elements rehashed.
**No new dependencies**.
**See**: examples.md for concrete walkthrough of merge vs link scenarios.

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | Unified provenance; removed legacy Constraints; cleaner identity |
| II. TDD | PASS | Test-alongside |
| III. API-First Design | PASS | Identity model documented before implementation |
| IV. Observability | PASS | Enrichment provenance on every entity |
| V. Versioning & Stability | PASS | Breaking; not released |
| VI. Environment Isolation | PASS | No changes |
| Evaluation Record | PASS | Phase 8 records results in eval-record.md |

## Phase 1: Unify Registry Entity Model

**Goal**: All 4 entity types share a consistent structure. Fix gaps from examples.md review.

| File | Change |
|------|--------|
| `models.py` | REMOVE `ontology_term` from SemanticIdentity |
| `models.py` | REMOVE `Constraints` model entirely; move `pattern: str \| None` to SemanticIdentity |
| `models.py` | ADD `description: str \| None` to SemanticIdentity, ValueSemanticIdentity, SchemaIdentity, ValueSetIdentity (NOT in hash for ontology-anchored; IN hash for structural fallback) |
| `models.py` | ADD `ontology_annotations: list[OntologyAnnotation] \| None` to SchemaIdentity and ValueSetIdentity |
| `models.py` | REMOVE `SchemaProvenance` and `ValueProvenance` — use `ProvenanceEntry` for all entity types |
| `models.py` | UPDATE SchemaRecord: `provenance: list[ProvenanceEntry]` |
| `models.py` | UPDATE ValueConcept: `provenance: list[ProvenanceEntry]` |
| `models.py` | REMOVE `source_attribute` and `source_class` from SemanticIdentity (replaced by class + attribute + description in fallback hash) |
| `hashing.py` | UPDATE `_EXCLUDED_FROM_HASH`: add `description`, `ontology_annotations`; remove `ontology_term` (gone), `source_attribute`, `source_class` |
| `hashing.py` | ADD `compute_identity_hash(semantic, provenance, ontology_anchored: bool) -> str` — two-mode hash function |

**Unified registry entity structure** (all 4 types):
```
semantic:
  <type-specific fields>        # IN hash
  description: str | None       # IN hash (fallback only)
  ontology_annotations: [...]   # NOT in hash (except primary URI when anchored)
provenance:
  - source: str
    class: str                  # IN hash (fallback only)
    name: str                   # IN hash (fallback only)
    description: str | None
    generated_at: str | None
    attributed_to: str | None
    activity: str | None
    source_ref: SourceRef | None
```

## Phase 2: Two-Mode Hash Function

**Goal**: `compute_identity_hash()` with ontology-anchored and structural fallback modes.

| File | Change |
|------|--------|
| `hashing.py` | REWRITE `canonical_json()` to accept mode parameter |

**Ontology-anchored mode** (when primary annotation has skos:exactMatch or element_match):
```python
hash_input = {
    "data_type": ...,
    "unit": ...,
    "response_options": [...],  # sorted by value
    "min_value": ...,
    "max_value": ...,
    "pattern": ...,
    "type_ref": ...,
    "primary_ontology_uri": "http://purl.obolibrary.org/obo/NCIT_C25150",
}
```

**Structural fallback mode** (no high-precision ontology match):
```python
hash_input = {
    "data_type": ...,
    "unit": ...,
    "response_options": [...],
    "min_value": ...,
    "max_value": ...,
    "pattern": ...,
    "type_ref": ...,
    "class": "participant",          # from provenance
    "attribute": "age",              # from provenance
    "description": "Age in years",   # canonical description
}
```

## Phase 3: Staging Directory

**Goal**: Extract writes to `.staging/{run_id}/` with UUIDs, not content-addressed names.

| File | Change |
|------|--------|
| `ingest.py` | REWRITE — extract to staging dir with UUID filenames; no hashing at extraction time |
| `cli.py` | Pipeline generates run_id, creates staging dir |

## Phase 4: In-Place Enrichment

**Goal**: Enrich staged entities in-place. No new entities. Dependency-ordered.

| File | Change |
|------|--------|
| `enrich.py` | REWRITE — `enrich_all(staging_dir)`: (1) elements + values parallel, (2) valuesets, (3) schemas. Uses `_assign_ontology_annotations()` from 025. Updates files in-place. |

## Phase 5: Commit Stage

**Goal**: Rehash enriched entities → content-addressed filenames → registry.

| File | Change |
|------|--------|
| `commit.py` | NEW — `commit_staged(staging_dir, output_dir)`: for each entity, determine hash mode (ontology-anchored or fallback), compute hash, write to registry, merge duplicates, delete staging |

**Multi-annotation → single hash relationship**:
- Enrichment produces `ontology_annotations: list[OntologyAnnotation]` (multiple terms, 025 heuristic)
- Only the **primary** annotation (highest score with exactMatch/element_match) enters the hash
- All other annotations are metadata (for discovery, not identity)
- Fallback uses first provenance entry's class + attribute + description

**Commit logic**:
```
for each staged entity:
    annotations = entity.semantic.ontology_annotations  # list from 025 heuristic
    primary = find primary annotation with exactMatch/element_match
    if primary and primary.score >= threshold:
        mode = "ontology_anchored"  # primary URI in hash
        hash = compute_identity_hash(semantic, provenance, ontology_anchored=True)
    else:
        mode = "structural_fallback"  # class+attribute+description in hash
        hash = compute_identity_hash(semantic, provenance, ontology_anchored=False)

    filename = f"{name}_{hash[:12]}.yaml"
    if filename exists in registry:
        merge provenance
    else:
        write new file
    delete staged file
```

## Phase 6: Update Downstream (Transforms, Index, Similarity)

**Goal**: All downstream code uses new identity model.

| File | Change |
|------|--------|
| `transform.py` | Use primary ontology annotation URI for grouping (not removed ontology_term) |
| `similarity.py` | Use primary annotation for ontology match scoring |
| `index.py` | Build ontology index from ontology_annotations (not ontology_term) |
| `verify.py` | Use OntologyStore for verification (already done in 024) |
| `validation.py` | Update hash verification for two-mode hashing |

## Phase 7: Update All Extractors

**Goal**: Extractors produce entities without hashing (UUID staged).

| File | Change |
|------|--------|
| All adapters in `adapters/` | Remove any hash computation; output raw semantic + provenance |
| `adapters/docker_scripts/bids_extract.py` | Remove hash references |
| `adapters/docker_scripts/dandi_extract.py` | Remove hash references |

## Phase 8: Re-extraction + Evaluation

**Goal**: Full pipeline with new model. Verify against baseline.

| Step | Verification |
|------|-------------|
| Ontology refresh | Reuse cached store (13 ontologies, 2.99M terms) |
| Extract all 5 sources to staging | All entities have UUIDs, no hashes |
| Enrich (elements+values → valuesets → schemas) | Ontology annotations present; no new entities |
| Commit to registry | Content-addressed filenames; duplicates merged |
| **Element count** | Should be < 7,756 (cross-source merges expected where identical) |
| **Transform count** | Should be proportional to unique ontology concept pairs |
| eval-record.md | Full comparison table vs 2026-03-21 baseline |

**Expected improvements**:
- Fewer elements (cross-source merge where structurally + semantically identical)
- Cleaner transforms (no identity transforms between elements that should have merged)
- Consistent provenance model across all entity types
- No legacy Constraints cruft

## Dependency Graph

```
Phase 1 (model unification)  → foundational
Phase 2 (two-mode hash)      → depends on Phase 1
Phase 3 (staging)            → depends on Phase 1
Phase 4 (enrichment)         → depends on Phase 3
Phase 5 (commit)             → depends on Phase 2 + Phase 4
Phase 6 (downstream)         → depends on Phase 2
Phase 7 (extractors)         → depends on Phase 3
Phase 8 (re-extract + eval)  → depends on all

Parallelizable: Phase 2 ‖ Phase 3; Phase 6 ‖ Phase 7
```

## Complexity Tracking

| Area | Complexity | Justification |
|------|-----------|---------------|
| Model unification | High | Touch all 4 entity models; remove legacy; unify provenance |
| Two-mode hash | Medium | New hash function with mode selection |
| Staging directory | Medium | Pipeline plumbing; UUID generation |
| In-place enrichment | Medium | Remove _create_enriched_element; 3-pass dependency order |
| Commit stage | High | Hash mode selection; merge logic; registry write |
| Downstream updates | Medium | 5 files reference old ontology_term field |
| Extractor updates | Low | Remove hash calls |
| Re-extraction | Low | Run pipeline, check counts |
