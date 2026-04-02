# Tasks: System Hardening

**Input**: Design documents from `/specs/038-system-hardening/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Format: `[ID] [P?] [Story] Description`

---

## Phase 1: Setup

**Purpose**: Shared models, evidence chain infrastructure

- [X] T001 Add EvidenceChain TypedDict/dataclass to library models for embedding in annotations and proposals in library/src/undata_library/models.py
- [X] T002 Add audit_service.py helper that writes AuditLog entries with agent, activity, entity_type, entity_ref, details in backend/src/services/audit_service.py
- [X] T003 Add EvidenceChain display component showing similarity score, verified URI badge, reasoning text in frontend/components/EvidenceChain.tsx

**Checkpoint**: Evidence chain data structure and audit writer ready

---

## Phase 2: Foundational

**Purpose**: Audit log wiring — every mutation must record an audit entry

- [X] T004 Wire audit_service.write_audit() into all existing GraphQL mutations (resolveFlag, updateElement, approveAnnotation, rejectAnnotation, versionElement, approveIngestion, rejectIngestion, reviewProposal) in backend/src/graphql/resolvers.py
- [X] T005 Add auditLog GraphQL query and AuditLogEntry type in backend/src/graphql/types.py, resolvers.py, and schema.py

**Checkpoint**: Every mutation creates an audit trail; audit log queryable

---

## Phase 3: User Story 1 — Live LLM Curation Chat (Priority: P1) 🎯 MVP

**Goal**: Chat processes messages via LLM with entity context; auto-suggests improvements on load

**Independent Test**: Send message in chat → LLM responds with entity-specific suggestions → proposals appear as diffs with evidence chains

- [X] T006 [US1] Verify chat_service.py processes messages end-to-end — test with OLLAMA_HOST or OPENAI_API_KEY configured in backend/src/services/chat_service.py
- [X] T007 [US1] Add auto-suggest on entity load — when chat right panel loads an entity, automatically send a system prompt "suggest improvements for this entity" to the LLM in frontend/app/curation/chat/page.tsx
- [X] T008 [US1] Generate EvidenceChain for every enrichment annotation — add similarity_score, source_text, target_term_uri/label/definition, uri_verified, reasoning to annotation dicts in library/src/undata_library/enrich.py
- [X] T009 [US1] Display EvidenceChain in proposal diffs and annotation chips — show score, URI badge, reasoning expandable in frontend/components/EvidenceChain.tsx and frontend/components/EntityDetailLayout.tsx
- [X] T010 [US1] Add evidence field to LLMEnrichmentProposal — LLM proposals include reasoning text and validated URI in backend/src/services/enrichment_service.py

**Checkpoint**: Chat responds with entity-aware suggestions; evidence chains visible on all proposals

---

## Phase 4: User Story 2 — Name-Based Transform Generation (Priority: P1)

**Goal**: Transforms detected by name similarity across sources; many-to-one supported

**Independent Test**: Run transform pipeline → 100+ transforms created (up from 15)

- [X] T011 [US2] Add name-based matching to transform pipeline — group elements by provenance name (case-insensitive), create transforms for cross-source matches with type compatibility check in library/src/undata_library/transform.py
- [X] T012 [US2] Add embedding similarity matching — compute cosine similarity between cross-source element pairs, create transforms above threshold (0.8) in library/src/undata_library/transform.py
- [X] T013 [US2] Extend TransformRecord with source_elements list for many-to-one mappings in library/src/undata_library/models.py
- [X] T014 [US2] Update Transform DB model and GraphQL type with source_elements field in backend/src/db/models.py and backend/src/graphql/types.py
- [X] T015 [US2] Add unit tests for name-based and embedding-based transform matching in library/tests/test_transform.py

**Checkpoint**: 100+ transforms generated; many-to-one model works

---

## Phase 5: User Story 3 — Additional Data Sources (Priority: P1)

**Goal**: Ingest from OpenNeuro, ReproSchema, NDA, stats repos

**Independent Test**: Ingest 10 OpenNeuro datasets + ReproSchema library + NDA structure → new entities in registry

- [X] T016 [US3] Implement NDA data dictionary adapter — fetch from NDA API, extract elements with description, type, valueRange in library/src/undata_library/adapters/nda.py
- [X] T017 [US3] Register NDA adapter in adapter registry in library/src/undata_library/adapters/registry.py
- [X] T018 [US3] Test end-to-end: ingest ds000228 from OpenNeuro via datalad, verify elements from participants.tsv and phenotype/*.tsv
- [X] T019 [US3] Test end-to-end: ingest reproschema-library, verify activities→schemas and items→elements
- [X] T020 [US3] Regenerate full registry at ~/.cache/undata/registry with all sources including OpenNeuro samples + ReproSchema

**Checkpoint**: Registry includes entities from 7+ sources

---

## Phase 6: User Story 4 — Search Modes (Priority: P2)

**Goal**: Search page with lexical/semantic/both toggle

**Independent Test**: Search "brain area" in semantic mode → finds "brain_region"

- [X] T021 [US4] Add SearchMode enum (LEXICAL, SEMANTIC, BOTH) to backend GraphQL types in backend/src/graphql/types.py
- [X] T022 [US4] Implement semantic search in resolve_search — encode query with sentence-transformers, find nearest embeddings via pgvector in backend/src/graphql/resolvers.py
- [X] T023 [US4] Add mode toggle (radio buttons: Lexical | Semantic | Both) to search page in frontend/app/search/page.tsx
- [X] T024 [US4] Pass mode variable to SEARCH GraphQL query in frontend/graphql/queries.ts

**Checkpoint**: Semantic search returns conceptually related results

---

## Phase 7: User Story 5 — Ontology Admin + NCBITaxon Filter (Priority: P2)

**Goal**: Admin page shows loaded ontologies; NCBITaxon filtered to relevant species

**Independent Test**: /admin/ontologies shows ontologies with term counts from pyoxigraph

- [X] T025 [US5] Add ontologyStoreInfo GraphQL query that reads from pyoxigraph OntologyStore.list_loaded() in backend/src/graphql/resolvers.py and schema.py
- [X] T026 [US5] Update ontology admin page to use ontologyStoreInfo instead of ontologySources DB query in frontend/app/admin/ontologies/page.tsx
- [X] T027 [US5] Implement NCBITaxon species filter — when building embedding index, include only neuroscience-relevant species (list of ~20 taxon IDs) in library/src/undata_library/ontology_store.py
- [X] T028 [US5] Load HoMBA from brain-bican GitHub releases (attempt OWL RDF/XML; fallback to TTL conversion) in library/src/undata_library/ontology_fetch.py

**Checkpoint**: Admin shows all ontologies; NCBITaxon filtered in embeddings

---

## Phase 8: User Story 6 — Server-Side Sorting + Infinite Scroll (Priority: P2)

**Goal**: All browse pages sort server-side; infinite scroll loads automatically

**Independent Test**: Click "Unit" column → server returns sorted results. Scroll → next page loads.

- [X] T029 [US6] Add sortBy/sortOrder params to browseSchemas, browseValues, browseValuesets resolvers in backend/src/graphql/resolvers.py
- [X] T030 [US6] Add sortBy/sortOrder to BROWSE_SCHEMAS, BROWSE_VALUES, BROWSE_VALUESETS GraphQL queries in frontend/graphql/queries.ts
- [X] T031 [US6] Wire onSortChange to schemas, values, valuesets browse pages (matching elements page pattern) in frontend/app/schemas/page.tsx, values/page.tsx, valuesets/page.tsx
- [ ] T032 [US6] Verify infinite scroll works on all browse pages — test with full registry loaded

**Checkpoint**: All pages sort server-side; infinite scroll loads smoothly

---

## Phase 9: User Story 7 — Audit Log + Downloads (Priority: P3)

**Goal**: Audit trail for all mutations; nightly exports with download page

**Independent Test**: Resolve a flag → audit entry created. Visit /downloads → see archive.

- [X] T033 [US7] Implement nightly_export.py background task — scheduled daily, calls export_service, creates Release record in backend/src/services/nightly_export.py
- [X] T034 [US7] Add static file serving for export archives at /api/downloads/ in backend/src/main.py
- [X] T035 [US7] Create download page listing releases with version, date, size, entity counts, download link in frontend/app/downloads/page.tsx
- [X] T036 [US7] Add "Downloads" link to sidebar in frontend/components/Sidebar.tsx

**Checkpoint**: Nightly export runs; download page lists releases

---

## Phase 10: User Story 8 — CI + Pipeline Maintenance (Priority: P3)

**Goal**: CI uses Node.js 24; vector index auto-rebuilds; LLM verifies borderline candidates

**Independent Test**: CI runs without warnings. Add ontology → index rebuilds.

- [X] T037 [P] [US8] Update GitHub Actions workflows to v5 action versions (checkout, setup-node, setup-python) in .github/workflows/*.yml
- [X] T038 [US8] Add ontology vector index staleness check — if ontology store checksum differs from index checksum, auto-rebuild in library/src/undata_library/enrich.py
- [X] T039 [US8] Implement LLM-assisted enrichment for borderline candidates (0.5-0.7 score) — batch verify via litellm with evidence chain generation in library/src/undata_library/llm_enrich.py

**Checkpoint**: CI green without warnings; index auto-rebuilds; LLM verifies candidates

---

## Phase 11: User Story 9 — Versioned Dependency Management (Priority: P1)

**Goal**: Auto-detect ontology/source version changes, re-enrich, record provenance

**Independent Test**: Update an ontology → system detects change → re-enriches affected entities

- [X] T040 [US9] Implement version_check.py — iterate registered ontology/source URLs, compare checksums, report changes in library/src/undata_library/version_check.py
- [X] T041 [US9] Implement version_service.py — scheduled check, trigger re-enrichment for changed ontologies, record VersionTransition in provenance in backend/src/services/version_service.py
- [X] T042 [US9] Add checkDependencyVersions GraphQL mutation in backend/src/graphql/schema.py
- [X] T043 [US9] Ensure re-enrichment preserves curator-approved annotations (curated_annotations field check) in library/src/undata_library/enrich.py

**Checkpoint**: Version changes detected; affected entities re-enriched with provenance

---

## Phase 12: Polish

**Purpose**: Final verification, seed data update

- [X] T044 Regenerate curated seed subset from full registry (with deduped flags, sha256 entity_refs)
- [ ] T045 Run quickstart.md validation for all 9 user stories
- [ ] T046 [P] Verify all browse pages: server-side sort + infinite scroll + source filter + search
- [ ] T047 [P] Verify curation queue detail panel shows evidence chains for flagged entities

---

## Dependencies & Execution Order

- **Setup + Foundational (Phase 1-2)**: Start immediately
- **US1 LLM Chat (Phase 3)**: After Foundational — MVP
- **US2 Transforms (Phase 4)**: After Setup — independent of US1
- **US3 Sources (Phase 5)**: After Setup — independent
- **US4 Search (Phase 6)**: After Setup (needs pgvector embeddings)
- **US5 Ontology (Phase 7)**: After Setup — independent
- **US6 Sorting (Phase 8)**: After Setup — independent
- **US7 Audit+Downloads (Phase 9)**: After Foundational (needs audit service)
- **US8 CI+Pipeline (Phase 10)**: Independent
- **US9 Versioning (Phase 11)**: After US5 (needs ontology checksum infrastructure)
- **Polish (Phase 12)**: After all stories

### Parallel Opportunities

- T037 (CI update) — fully independent
- US2, US3, US5, US6 can run in parallel after Setup
- T046, T047 (polish verification) — independent

---

## Implementation Strategy

### MVP First (US1)

1. Setup + Foundational → audit + evidence chain infrastructure
2. US1 → LLM chat wiring + auto-suggest + evidence display
3. **STOP and VALIDATE**: Chat works end-to-end with evidence chains

### Incremental Delivery

1. Setup + Foundational → infrastructure
2. US1 → LLM chat (MVP)
3. US2 + US3 (parallel) → transforms + sources
4. US4 + US5 + US6 (parallel) → search + ontology + sorting
5. US7 → audit log + downloads
6. US8 + US9 → CI + versioning
7. Polish → verification
