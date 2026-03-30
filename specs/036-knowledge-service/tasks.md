# Tasks: Knowledge Service

**Input**: Design documents from `/specs/036-knowledge-service/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US7)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Dependencies, shared DB models, ontology store extension

- [X] T001 Add datalad and pydicom to library dependencies in library/pyproject.toml
- [X] T002 Add OntologySource, IngestionJob, LLMEnrichmentProposal DB models to backend/src/db/models.py
- [X] T003 Add Strawberry GraphQL types for OntologySource, IngestionJob, LLMEnrichmentProposal in backend/src/graphql/types.py
- [X] T004 Extend ontology store with source registration — add_source(), refresh_source(), list_sources(), toggle_active() in library/src/undata_library/ontology_store.py
- [X] T005 Add OntologySourceConfig and IngestionJobConfig pydantic models in library/src/undata_library/models.py

**Checkpoint**: DB models exist, ontology store supports source management

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Ontology loading infrastructure that all stories depend on

- [X] T006 Implement OWL/OBO/TTL ontology loader that reads from URL or local path via fetch_and_load_source() in library/src/undata_library/ontology_fetch.py
- [X] T007 Implement CLI command: `ontology add` (name, url, format) in library/src/undata_library/cli.py

**Checkpoint**: Can add and refresh ontologies from CLI

---

## Phase 3: User Story 1 — Domain-Specific Ontologies (Priority: P1) 🎯 MVP

**Goal**: HoMBA, NIDM, DICOM, RadLex, ReproSchema loaded into ontology store; enrichment coverage >40%

**Independent Test**: `uv run undata-library ontology list` shows 4+ new ontologies with combined >50K terms; re-enrichment of BIDS elements produces >40% annotation coverage

- [X] T008 [P] [US1] Add HoMBA ontology config — URL registered in DOMAIN_ONTOLOGIES in library/src/undata_library/ontology_fetch.py
- [X] T009 [P] [US1] Add NIDM-Terms config — OWL URL registered in DOMAIN_ONTOLOGIES in library/src/undata_library/ontology_fetch.py
- [X] T010 [P] [US1] Create DICOM TTL generator — extract all tags from pydicom.datadict, generate TTL with URIs in library/src/undata_library/adapters/standalone_scripts/dicom_to_ttl.py
- [X] T011 [P] [US1] Add RadLex ontology config — OWL URL registered in DOMAIN_ONTOLOGIES in library/src/undata_library/ontology_fetch.py
- [ ] T012 [US1] Re-run enrichment on BIDS+NWB+DANDI elements with expanded ontology store, then assert annotated_count/total_count > 0.40 via `undata-library ontology info` and `validate-ingestion` in library/src/undata_library/enrich.py
- [ ] T013 [US1] Add unit test verifying ontology term counts after loading all 4 new sources in library/tests/test_ontology_sources.py
- [ ] T013a [US1] Add coverage regression test — assert enrichment produces annotations for >40% of elements, fails if coverage drops below threshold in library/tests/test_enrichment_coverage.py

**Checkpoint**: Ontology store has >50K new terms; enrichment coverage exceeds 40%

---

## Phase 4: User Story 2 — OpenNeuro & ReproSchema Adapters (Priority: P1)

**Goal**: Ingest schema descriptors from OpenNeuro datasets (via datalad) and ReproSchema library

**Independent Test**: `uv run undata-library ingest --source openneuro --path ds000228` produces elements from participants.tsv and phenotype TSVs

- [X] T014 [US2] Implement OpenNeuro adapter — datalad clone, scan for all TSV/CSV files, read JSON sidecars for column descriptions, extract elements with data types inferred from values in library/src/undata_library/adapters/openneuro.py
- [X] T015 [US2] Implement ReproSchema adapter — parse activity JSON-LD as schemas (CLASS), item JSON-LD as elements (ATTRIBUTE), response options as valuesets in library/src/undata_library/adapters/reproschema.py
- [X] T016 [US2] Register openneuro and reproschema adapters in library/src/undata_library/adapters/registry.py
- [ ] T017 [US2] Add unit tests for OpenNeuro adapter with a mock dataset structure in library/tests/test_openneuro_adapter.py
- [ ] T018 [US2] Add unit tests for ReproSchema adapter with sample activity/item files in library/tests/test_reproschema_adapter.py
- [ ] T019 [US2] Test full pipeline: ingest ds000228 from OpenNeuro, verify elements extracted from participants.tsv and phenotype/*.tsv

**Checkpoint**: OpenNeuro and ReproSchema adapters produce valid entities

---

## Phase 5: User Story 3 — Enrichment Review & Versioning (Priority: P1)

**Goal**: Curators can approve/reject annotations; semantic field changes create new element versions

**Independent Test**: Reject an annotation on an element → annotation removed, provenance recorded; change unit → new sha256 created, curation_update transform links old→new

- [X] T020 [US3] Add curated_annotations JSONB field and superseded_by field to Element model in backend/src/db/models.py
- [X] T021 [US3] Extend enrichment pipeline to skip entities with curated_annotations (do not overwrite approved annotations) in library/src/undata_library/enrich.py
- [ ] T022 [US3] Implement element versioning — when a semantic field changes via curation, create new element with new sha256, mark old as superseded, create curation_update transform in backend/src/graphql/resolvers.py
- [X] T023 [US3] Add GraphQL mutations: approveAnnotation, rejectAnnotation in backend/src/graphql/schema.py
- [ ] T023a [US3] Implement requestReEnrichment service — re-run enrichment for a single element using latest ontology store, return proposed new annotations as diff in backend/src/graphql/resolvers.py
- [ ] T024 [US3] Add approve/reject buttons to annotation chips on element detail page in frontend/app/elements/[sha256]/page.tsx (or via EntityDetailLayout)
- [ ] T025 [US3] Add unit test for curated annotation protection during re-enrichment in library/tests/test_enrich.py

**Checkpoint**: Curators can approve/reject; semantic changes produce new versions with transforms

---

## Phase 6: User Story 4 — Ontology Store Management (Priority: P2)

**Goal**: Admin interface for ontology listing, add, refresh, toggle active

**Independent Test**: Open /admin/ontologies → see table of loaded ontologies with term counts and refresh button

- [X] T026 [US4] Add GraphQL resolvers for ontologySources, ingestionQueue, enrichmentProposals in backend/src/graphql/resolvers.py
- [X] T027 [US4] Wire ontology/ingestion/enrichment queries into GraphQL schema in backend/src/graphql/schema.py
- [X] T028 [US4] Add GraphQL queries for ontology, ingestion, enrichment in frontend/graphql/queries.ts
- [X] T029 [US4] Create ontology admin page with term counts, format, status, refresh dates in frontend/app/admin/ontologies/page.tsx
- [X] T030 [US4] Add "Admin" section to sidebar with Ontologies and Ingestion links in frontend/components/Sidebar.tsx

**Checkpoint**: Admin can view, add, refresh, and toggle ontology sources

---

## Phase 7: User Story 5+6 — Source Discovery & Ingestion Queue (Priority: P1+P2)

**Goal**: Automated discovery from OpenNeuro/DANDI; ingestion queue with auto-ingest for approved sources

**Independent Test**: New OpenNeuro dataset appears → system discovers it → auto-ingests via BIDS adapter → elements appear in registry

- [X] T031 [US6] Implement discovery scanner — poll OpenNeuro GraphQL API and DANDI API for new datasets since last check in library/src/undata_library/discovery.py
- [ ] T032 [US6] Implement discovery background service — schedule daily scans, create IngestionJob records for discovered datasets in backend/src/services/discovery_service.py
- [ ] T033 [US6] Implement auto-ingest logic — when IngestionJob is from pre-approved source with known adapter, auto-approve and run pipeline in backend/src/services/discovery_service.py
- [ ] T034 [US5] Add GraphQL resolvers for ingestionQueue, approveIngestion, rejectIngestion, queueIngestion in backend/src/graphql/resolvers.py
- [ ] T035 [US5] Wire ingestion queries and mutations into GraphQL schema in backend/src/graphql/schema.py
- [ ] T036 [US5] Add GraphQL queries for ingestion queue in frontend/graphql/queries.ts
- [X] T037 [US5] Create ingestion queue page — table of jobs with status, adapter, entity counts, approve/reject actions in frontend/app/admin/ingestion/page.tsx
- [ ] T038 [US5] Integrate ingestion trigger into curation chat — LLM tool "trigger_ingestion" for curator requests in backend/src/tools/enrichment_tools.py

**Checkpoint**: Discovery finds new datasets; approved sources auto-ingest; queue UI shows all jobs

---

## Phase 8: User Story 7 — LLM Enrichment Skills (Priority: P2)

**Goal**: LLM-powered annotation, unit inference, alignment, description generation with batch mode

**Independent Test**: Ask chat "suggest better annotations for EchoTime" → LLM proposes DICOM/NIDM annotation with reasoning

- [ ] T039 [US7] Add LLMEnrichmentProposal GraphQL resolvers: enrichmentProposals, requestEnrichment, batchEnrichment, reviewProposal in backend/src/graphql/resolvers.py
- [ ] T040 [US7] Wire LLM enrichment queries and mutations into GraphQL schema in backend/src/graphql/schema.py
- [ ] T041 [P] [US7] Implement suggest_ontology_annotation LLM skill — search ontology store, propose best match with reasoning in backend/src/services/enrichment_service.py
- [ ] T042 [P] [US7] Implement suggest_unit LLM skill — infer unit from name+description+context with justification in backend/src/services/enrichment_service.py
- [ ] T043 [P] [US7] Implement assess_alignment LLM skill — compare two elements, assess if same concept or different variants in backend/src/services/enrichment_service.py
- [ ] T044 [P] [US7] Implement generate_description LLM skill — create description from element name, type, unit, source context in backend/src/services/enrichment_service.py
- [ ] T045 [US7] Implement batch enrichment orchestrator — queue elements, process with rate limiting and token budget tracking in backend/src/services/enrichment_service.py
- [ ] T046 [US7] Add LLM enrichment tool definitions for curation chat integration in backend/src/tools/enrichment_tools.py
- [ ] T047 [US7] Add enrichment proposals UI — show pending proposals per entity with approve/reject in frontend (extend entity detail pages)
- [ ] T048 [US7] Add frontend GraphQL queries for enrichment proposals in frontend/graphql/queries.ts

**Checkpoint**: LLM skills propose annotations with reasoning; batch mode processes unannotated elements

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Final integration, verification, seed data regeneration

- [ ] T049 Regenerate seed data with expanded ontology store and new sources
- [ ] T050 Run quickstart.md validation — verify all ontology, ingestion, and enrichment operations
- [ ] T051 [P] Verify ontology admin page and ingestion queue UI work end-to-end
- [ ] T052 [P] Verify LLM enrichment via chat produces proposals with reasoning
- [ ] T053 Verify enrichment coverage exceeds 40% with expanded ontology store

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup (T001-T005)
- **US1 (Phase 3)**: Depends on Foundational — MVP starting point
- **US2 (Phase 4)**: Depends on Foundational — can run in parallel with US1
- **US3 (Phase 5)**: Depends on US1 (needs enrichment working to review annotations)
- **US4 (Phase 6)**: Depends on US1 (needs ontology sources in DB)
- **US5+US6 (Phase 7)**: Depends on US2 (needs adapters working for auto-ingest)
- **US7 (Phase 8)**: Depends on US1 (needs ontology store for LLM skills)
- **Polish (Phase 9)**: Depends on all stories complete

### User Story Dependencies

- **US1 (Ontologies)**: Foundation only — MVP
- **US2 (Adapters)**: Foundation only — can parallel with US1
- **US3 (Review/Versioning)**: Needs US1 (annotations to review)
- **US4 (Ontology Admin)**: Needs US1 (sources to manage)
- **US5+US6 (Discovery/Queue)**: Needs US2 (adapters for auto-ingest)
- **US7 (LLM Skills)**: Needs US1 (ontology store for skill queries)

### Parallel Opportunities

- T008, T009, T010, T011 (US1 ontology loaders) — all different ontologies, fully parallel
- T014, T015 (US2 adapters) — different adapter files, parallel
- T041, T042, T043, T044 (US7 LLM skills) — independent skills, parallel
- US1 and US2 can run in parallel after Foundational phase

---

## Implementation Strategy

### MVP First (US1)

1. Complete Phase 1: Setup (dependencies, DB models)
2. Complete Phase 2: Foundational (ontology store extension)
3. Complete Phase 3: US1 (load 4 ontologies, verify >40% coverage)
4. **STOP and VALIDATE**: `ontology list` shows new sources; enrichment coverage improved

### Incremental Delivery

1. Setup + Foundational → infrastructure ready
2. US1 → ontology store expanded (MVP)
3. US2 → OpenNeuro + ReproSchema adapters
4. US3 → annotation review + versioning
5. US4 → ontology admin UI
6. US5+US6 → automated discovery + ingestion queue
7. US7 → LLM enrichment skills
8. Polish → verification

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Each user story is independently testable at its checkpoint
- Commit after each task or logical group
- Ontology files may be large (RadLex ~50MB) — ensure Docker image handles this
- LLM enrichment requires API keys (OPENAI_API_KEY or OLLAMA_HOST) — document in .env
