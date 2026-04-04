# Implementation Plan: Cross-Source Alignment

**Branch**: `041-cross-source-alignment` | **Date**: 2026-04-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/041-cross-source-alignment/spec.md`

## Summary

Improve the alignment pipeline to merge duplicate entities across sources and datasets into canonical entities. Convert all 8 adapters to produce LinkML SchemaDefinitions, build SchemaView per source for pre-serialization slot deduplication, implement multi-signal cross-source alignment (name blocking + embedding k-NN + ontology + alias), persist alignment as sha256-based graph relations on entities, add search-driven alignment feedback, and expose alignment groups in the UI.

## Technical Context

**Language/Version**: Python 3.14 (library, backend) + TypeScript (frontend)
**Primary Dependencies**: linkml-runtime (SchemaView), sentence-transformers (embeddings), numpy (k-NN), strawberry-graphql, Apollo Client
**Storage**: ParquetStore (library pipeline) → PostgreSQL + pgvector (backend)
**Testing**: pytest + pytest-asyncio (backend), vitest (frontend)
**Target Platform**: Linux/macOS workstation + Docker
**Project Type**: Library + Web service + Frontend
**Performance Goals**: Full alignment of 926K entities in <30 minutes; UI entity load <2 seconds
**Constraints**: No new external services; alignment runs as pipeline step; all adapters must use LinkML
**Scale/Scope**: 926K entities from 8 sources → ~370K canonical elements post-alignment

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | SchemaView replaces manual dedup; alignment uses existing signals (embeddings, ontology). No new abstractions beyond what's needed. |
| II. TDD | PASS | Tests for alignment scoring, adapter LinkML output, and graph persistence. |
| III. API-First Design | PASS | Contracts defined for alignment pipeline, adapter interface, and GraphQL extensions. |
| IV. Observability | PASS | Alignment report logs group counts, conflict counts, and per-source stats. |
| V. No Deprecation | PASS | Direct replacement of old alignment logic; no compatibility shims. |
| VI. Environment Isolation | PASS | All Python via uv; no new bridge venvs needed (linkml-runtime supports 3.14). |
| VII. Developer Experience | PASS | `uv run undata-library align` works standalone; docker compose up includes alignment in pipeline. |

## Project Structure

### Documentation (this feature)

```text
specs/041-cross-source-alignment/
├── spec.md
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── alignment-pipeline.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (files touched)

```text
library/src/undata_library/
├── adapters/
│   ├── reproschema.py       # MODIFY: add to_linkml() implementation
│   ├── nda.py               # MODIFY: add to_linkml() implementation
│   ├── openneuro.py         # MODIFY: add to_linkml() implementation
│   ├── bids.py              # MODIFY: add to_linkml() (currently direct extraction)
│   ├── linkml_builder.py    # MODIFY: add alias support to add_slot()
│   ├── linkml.py            # MODIFY: use SchemaView for slot traversal
│   └── extractor.py         # MODIFY: build SchemaView before extraction
├── align.py                 # REWRITE: multi-signal alignment with graph persistence
├── alias_detection.py       # MODIFY: integrate into alignment scoring
├── similarity.py            # MODIFY: add name normalization signal
├── storage/
│   └── parquet_store.py     # MODIFY: support aligned_to/aligned_members fields
└── cli.py                   # MODIFY: add align subcommand options

backend/src/
├── graphql/resolvers.py     # MODIFY: expose alignment fields, record search candidates
├── storage/database_backend.py  # MODIFY: import alignment fields
└── db/models.py             # MODIFY: add alignment columns to entity tables

frontend/
├── app/elements/[id]/page.tsx   # MODIFY: show "Aligned From" section
├── app/schemas/[id]/page.tsx    # MODIFY: show alignment info
├── app/values/[id]/page.tsx     # MODIFY: show alignment info
├── app/valuesets/[id]/page.tsx  # MODIFY: show alignment info
└── app/search/page.tsx          # MODIFY: trigger candidate recording
```

**Structure Decision**: Extends existing library/backend/frontend structure. No new top-level directories. Alignment logic stays in library; backend exposes via GraphQL; frontend displays.

## Architecture

### Phase 1: Pre-Serialization Dedup (SchemaView)

```
Adapter.to_linkml() → SchemaDefinition
         ↓
SchemaView(schema_def)
         ↓
  ┌──────┴──────┐
  │ Slot dedup:  │
  │ - same name  │
  │ - aliases    │
  │ - slot_usage │
  └──────┬──────┘
         ↓
extract_from_schema_definition() → ClassifiedEntity[]
         ↓
ParquetStore (1 entity per unique slot, combined provenance)
```

### Phase 2: Post-Commit Alignment

```
All sources committed → ParquetStore entities with embeddings
         ↓
  ┌──────────────────────────┐
  │ Candidate Generation:     │
  │ 1. Name blocking          │
  │    (normalize → exact)    │
  │ 2. Embedding k-NN         │
  │    (numpy dot product)    │
  │ 3. Search candidates      │
  │    (alignment_candidates) │
  └──────────┬───────────────┘
             ↓
  ┌──────────────────────────┐
  │ Multi-Signal Scoring:     │
  │ - name_sim (0.3)          │
  │ - embedding_sim (0.3)     │
  │ - ontology_overlap (0.25) │
  │ - alias_match (0.15)      │
  └──────────┬───────────────┘
             ↓
  ┌──────────────────────────┐
  │ Group Formation:          │
  │ - Union-find on pairs     │
  │   above threshold (0.7)   │
  │ - Range compatibility     │
  │   check (must match)      │
  │ - Conflict detection      │
  └──────────┬───────────────┘
             ↓
  ┌──────────────────────────┐
  │ Canonical Designation:    │
  │ - Identical → earliest    │
  │ - Merge needed → new      │
  │ - Write aligned_to /      │
  │   aligned_members fields  │
  └──────────────────────────┘
```

### Phase 3: Search Feedback

```
User search (semantic/both mode)
         ↓
Search resolver returns results
         ↓
  ┌────────────────────────────┐
  │ If 2+ unaligned entities    │
  │ with similarity > 0.8:     │
  │ → Record as candidates     │
  │   in alignment_candidates  │
  │   table/parquet            │
  └────────────────────────────┘
         ↓
Next pipeline run evaluates candidates
```

## Complexity Tracking

No constitution violations. All changes follow Simplicity First — using existing LinkML infrastructure (SchemaView), existing embedding infrastructure (sentence-transformers), and existing storage (ParquetStore + PostgreSQL).
