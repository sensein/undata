# Implementation Plan: Rich Data Element Model

**Branch**: `018-rich-data-model` | **Date**: 2026-03-17 (updated 2026-03-20) | **Spec**: spec.md

## Summary

Enrich the library's data element model with reproschema-aligned fields, W3C PROV-O
provenance, ontology verification, semantic similarity scoring, and valueset-based
alias detection. Add a **semantic embedding layer** (class + name + description →
precomputed embeddings in parquet) powering alias detection, ontology alignment, and
verification. Define the **ingest → enrich → align** pipeline as composable CLI commands.

## Technical Context

**Language/Version**: Python 3.14 (`requires-python = ">=3.14"`)
**Primary Dependencies**: pyyaml, pydantic 2.x, click, sentence-transformers (optional, for embeddings), pyarrow (for parquet embedding store), requests (for OLS API)
**Storage**: File-based (YAML elements/values/schemas + parquet embedding stores)
**Testing**: pytest + pytest-asyncio
**Target Platform**: CLI tool (cross-platform)
**Project Type**: Library/CLI
**Performance Goals**: enrich 3000 elements < 60s, align 3000 elements < 5 min, similarity < 100ms per pair, embedding generation < 30s for 3000 elements
**Constraints**: Offline-capable (bundled ontology cache + precomputed embeddings), no live API calls during enrich/align
**Scale/Scope**: ~3000 elements across 5 sources

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | Reuses existing similarity/alias detection; embedding layer is a single module with parquet I/O |
| II. TDD | PASS | Test tasks per phase (test-alongside pattern established in Phases 1–7); test fixtures written before implementation functions |
| III. API-First Design | PASS | CLI contracts defined in spec (FR-015–FR-036) |
| IV. Observability | PASS | Pipeline reports stats per step; structured logging |
| V. Versioning & Stability | PASS | New CLI commands, no breaking changes to existing |
| VI. Environment Isolation | PASS | All via `uv run`; pyarrow is base dep; sentence-transformers optional (`[embeddings]` extra) |
| Git Commit Discipline | PASS | Commit per phase |

## Implementation Status (Phases 1–5 COMPLETE)

Phases 1–5 from the original plan are fully implemented:

- **Phase 1** (SemanticIdentity + PROV-O): COMPLETE — models.py, hashing.py, extractors updated
- **Phase 2** (Underscore Reclassification): COMPLETE — AIND/BIDS extractors filter `_` prefixed entries
- **Phase 3** (Ontology Cache + Verification): COMPLETE — ontology_cache.py, ontology_fetch.py, verify.py, CLI commands
- **Phase 4** (Similarity + Alias Detection): COMPLETE — similarity.py, alias_detection.py, CLI commands
- **Phase 5** (Re-ingest + Backend Alignment): COMPLETE — backend SemanticInput aligned, frontend updated

## Phase 8: Semantic Embedding Layer (NEW)

**Goal**: Precomputed embeddings from `"{class} {name}: {description}"` stored in parquet,
used as the foundation for similarity scoring, ontology alignment, and alias detection.

**New module**: `library/src/undata_library/embeddings.py`

**Design** (FR-015 through FR-018):

1. **Embedding text construction**: For each element, build text from provenance entries:
   `"{class} {name}: {description}"`. Missing description gracefully omitted.
   For ontology terms: `"{label}: {synonym1}, {synonym2}, ..."`.

2. **Model management**: Configurable via `--model` flag (default `all-MiniLM-L6-v2`).
   Lazy-load model on first use (same pattern as existing `_EMBEDDING_MODEL` in similarity.py).
   Model name stored in parquet metadata for consistency validation on reload.

3. **Parquet storage** (`embeddings.parquet` at library root):
   - Columns: `uri` (string), `text` (string), `vector` (list[float32])
   - Metadata: `model`, `generated_at`
   - Optimized: float16 vectors for storage, float32 for computation

4. **Ontology embeddings** (`ontology-cache/embeddings.parquet`):
   - Columns: `term_uri` (string), `text` (string), `vector` (list[float32])
   - Generated during `ontology refresh` or explicit `embed` command

5. **Similarity integration**: Replace `name_sim` component (weight 0.3) in
   `compute_similarity()` with `semantic_embedding` cosine distance from precomputed
   vectors. Lookup by URI from parquet. Fallback to difflib if embeddings unavailable.

**CLI**: `undata-library embed [PATH] [--model MODEL] [--include-ontology]`

### Phase 8 File Changes

| File | Change |
|------|--------|
| `src/undata_library/embeddings.py` | NEW — `EmbeddingStore` class, `build_element_embeddings()`, `build_ontology_embeddings()`, `load_embeddings()`, `cosine_similarity()` |
| `src/undata_library/similarity.py` | MODIFY — replace `name_similarity()` with `semantic_embedding_similarity()` using precomputed vectors; keep difflib fallback |
| `src/undata_library/alias_detection.py` | MODIFY — pass embedding store to similarity scoring |
| `src/undata_library/cli.py` | ADD `embed` command |
| `tests/test_embeddings.py` | NEW — tests for text construction, parquet I/O, cosine similarity, model mismatch detection |

## Phase 9: Enrichment Pipeline (NEW)

**Goal**: `undata-library enrich` — post-ingestion enrichment of elements.

**Existing code to reuse**:
- `_resolve_response_option_uris()` in ingest.py — extract to standalone function
- `EmbeddingStore` from Phase 8 — ontology term matching via embedding distance
- `OntologyCache` — term metadata (labels, synonyms, deprecated status)

**New module**: `library/src/undata_library/enrich.py`

**Operations** (FR-023 through FR-029):

1. **Auto-assign ontology_term**: Compute cosine distance between element embedding and
   all ontology term embeddings (from `ontology-cache/embeddings.parquet`). Best match
   above threshold (default 0.7) assigned. This replaces the string-based label matching.
2. **Resolve response_options → ValueConcept URIs**: Scan library values/ directory, match
   by label/raw_value. Replace raw string choices with ValueConcept URIs where found.
3. **Auto-populate value_domain**: Map data_type → value_domain
   (string→text, integer/float→numeric, boolean→boolean, array/object→null).
   Override to `categorical` if response_options present.
4. **Identity-changing enrichment**: If ontology_term was assigned (changes hash), create
   new element file with new content-addressed URI. Add provenance entry with
   `derived_from: <old_uri>`, `activity: enrichment`,
   `attributed_to: urn:undata:enrichment-pipeline`.
   Old element file is NOT deleted.
5. **Regenerate embeddings**: After creating new elements, rebuild `embeddings.parquet`
   so alignment step has up-to-date vectors.
6. **Idempotency**: Skip elements where all enrichment operations produce no change.

**CLI**: `undata-library enrich [PATH] [--cache-dir DIR] [--threshold FLOAT] [--model MODEL] [--dry-run]`

**Output**: Stats dict `{enriched_new, enriched_unchanged, ontology_assigned, values_resolved, total}`

### Phase 9 File Changes

| File | Change |
|------|--------|
| `src/undata_library/enrich.py` | NEW — `enrich_elements()`, `_assign_ontology_term()`, `_resolve_response_options()`, `_populate_value_domain()`, `_create_enriched_element()` |
| `src/undata_library/cli.py` | ADD `enrich` command |
| `tests/test_enrich.py` | NEW — tests for all enrichment operations + idempotency + embedding-based ontology matching |

## Phase 10: Alignment Pipeline (NEW)

**Goal**: `undata-library align` — re-run alias detection post-enrichment using precomputed
embeddings, persist alias groups with provenance.

**Existing code to reuse**:
- `detect_aliases()` in alias_detection.py — pairwise similarity scanning
- `compute_similarity()` in similarity.py — now uses semantic embeddings (Phase 8)
- `EmbeddingStore` — precomputed vectors for fast similarity

**New module**: `library/src/undata_library/align.py`

**Operations** (FR-030 through FR-033):

1. **Run alias detection**: Call `detect_aliases()` using embeddings from `embeddings.parquet`.
2. **Form alias groups**: Group elements by transitive closure of `skos:exactMatch` pairs.
   Elements sharing the same content-addressed URI are aliases by design (same hash).
   `skos:closeMatch` pairs (0.8–0.95) recorded as candidate alias groups.
3. **Persist alignment report**: Write `alignment-report.yaml` to library root with:
   - `groups`: list of alias groups (each with member URIs, SKOS relation, confidence)
   - `ungrouped`: elements not in any alias group
   - `stats`: total pairs evaluated, groups formed, groups unchanged
   - `generated_at`, `attributed_to`
4. **Update provenance**: For each element newly added to an alias group, append a
   provenance entry with `activity: enrichment`,
   `attributed_to: urn:undata:alignment-pipeline`.
5. **Diff from previous**: If `alignment-report.yaml` already exists, compute diff
   (new groups, dissolved groups, changed groups) and include in report.

**CLI**: `undata-library align [PATH] [--threshold FLOAT] [--output FILE] [--dry-run]`

**Output**: Alignment report YAML + stats dict

### Phase 10 File Changes

| File | Change |
|------|--------|
| `src/undata_library/align.py` | NEW — `align_elements()`, `_form_alias_groups()`, `_persist_report()`, `_update_provenance()` |
| `src/undata_library/cli.py` | ADD `align` command |
| `tests/test_align.py` | NEW — tests for alias grouping, provenance updates, report generation, idempotency |

## Phase 11: Pipeline Orchestration (NEW)

**Goal**: `undata-library pipeline` — convenience command chaining ingest → enrich → align.

**Operations** (FR-034 through FR-036):

1. Chain `ingest_source()` → `enrich_elements()` → `align_elements()` in sequence.
2. Accept `--source` (required), `--path`, `--library-path`, `--model` (embedding model),
   `--skip-enrich`, `--skip-align`.
3. Report aggregate stats per step with elapsed time.

### Phase 9 File Changes

| File | Change |
|------|--------|
| `src/undata_library/cli.py` | ADD `pipeline` command |
| `tests/test_pipeline.py` | NEW — integration test for full pipeline, partial runs (--skip flags) |

## Project Structure

### Documentation (this feature)

```text
specs/018-rich-data-model/
├── spec.md              # Feature specification (updated with embedding layer + pipeline)
├── plan.md              # This file
└── tasks.md             # Task list (next step)
```

### Source Code (library)

```text
library/src/undata_library/
├── models.py            # EXISTING — SemanticIdentity, ProvenanceEntry, etc.
├── hashing.py           # EXISTING — content-addressed hashing
├── ingest.py            # EXISTING — ingestion pipeline
├── embeddings.py        # NEW (Phase 8) — embedding store (parquet I/O, model management)
├── enrich.py            # NEW (Phase 9) — enrichment pipeline
├── align.py             # NEW (Phase 10) — alignment pipeline
├── similarity.py        # EXISTING (MODIFIED Phase 8) — uses semantic embeddings
├── alias_detection.py   # EXISTING (MODIFIED Phase 8) — passes embedding store
├── ontology_cache.py    # EXISTING — bundled ontology term cache
├── ontology_fetch.py    # EXISTING — OLS API fetch
├── verify.py            # EXISTING — ontology alignment verification
├── index.py             # EXISTING — index + ontology-index builders
├── cli.py               # EXISTING — CLI entry points (add embed, enrich, align, pipeline)
├── diff.py              # EXISTING — provenance diff
├── validation.py        # EXISTING — YAML validation
├── export.py            # EXISTING — backend export
└── import_lib.py        # EXISTING — backend import
```

### Generated Artifacts (library root)

```text
library/
├── elements/                    # EXISTING — element YAML files
├── values/                      # EXISTING — value concept YAML files
├── schemas/                     # EXISTING — schema YAML files
├── embeddings.parquet           # NEW — element embeddings (uri, text, vector)
├── alignment-report.yaml        # NEW — alias groups + stats
├── ontology-cache/
│   ├── ncit.yaml                # EXISTING — ontology term data
│   ├── pato.yaml
│   ├── ...
│   └── embeddings.parquet       # NEW — ontology term embeddings
└── hash-registry.yaml           # EXISTING — content-addressed hash registry
```

## Dependency Graph

```
Phase 8  (embeddings) depends on: sentence-transformers (optional), pyarrow (base), ontology_cache
Phase 9  (enrich)    depends on: Phase 8 (embedding store), ontology_cache, ingest (response_option resolution)
Phase 10 (align)     depends on: Phase 9, Phase 8, alias_detection, similarity
Phase 11 (pipeline)  depends on: Phase 9 + Phase 10 + ingest
```

## Complexity Tracking

| Area | Complexity | Justification |
|------|-----------|---------------|
| Embedding store (parquet) | Medium | Parquet I/O with vector columns; model metadata management; float16 optimization |
| Embedding-based ontology matching | Medium | Cosine distance against ontology embeddings; threshold tuning |
| Enrichment identity fork | Medium | New element creation when hash changes; must handle provenance chain correctly |
| Alias group transitive closure | Medium | Graph algorithm for grouping; keep simple with union-find |
| Similarity refactor | Low | Replace name_sim with embedding lookup; keep same interface |
| Idempotency | Low | Compare before/after hash; skip if unchanged |
| Pipeline orchestration | Low | Sequential function calls with stats aggregation |

## Risks

| Risk | Mitigation |
|------|-----------|
| sentence-transformers not installed | Graceful fallback to difflib for similarity; warn user on first use |
| pyarrow not installed | Fail with clear error message pointing to `uv add pyarrow` |
| Ontology embedding matching produces false positives | Configurable threshold (default 0.7); dry-run mode for review |
| Enrichment creates too many new elements | Track `enriched_new` count; alert if > 50% of total |
| Model mismatch between stored and requested embeddings | Store model name in parquet metadata; warn and regenerate if mismatch |
| Embedding parquet grows large | Float16 storage; 3000 elements × 384 dims × 2 bytes ≈ 2.3 MB (well within limits) |
| Alias detection slow on large element sets | Precomputed embeddings + numpy vectorized cosine → O(n²) but with fast inner product |
