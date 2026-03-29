# Tasks: UX & UI Overhaul

**Input**: Design documents from `/specs/035-ux-overhaul/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US7)
- Include exact file paths in descriptions

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: PostgreSQL extensions, embedding infrastructure, shared DB columns

- [ ] T001 Create PostgreSQL init script enabling pgvector and pg_trgm extensions in backend/postgres-init/02-enable-extensions.sql
- [ ] T002 Add embedding vector(384) and search_tsv tsvector columns to Element, Schema, Value, ValueSet models in backend/src/db/models.py
- [ ] T003 Create embedding_service.py in backend/src/services/embedding_service.py — compute embeddings using sentence-transformers all-MiniLM-L6-v2, reusing library's encode logic
- [ ] T004 Update database_backend.py to compute and persist embeddings and search_tsv during entity write in backend/src/storage/database_backend.py
- [ ] T005 Update import_service.py to populate embeddings and search_tsv during seed import in backend/src/services/import_service.py

**Checkpoint**: Database supports vector similarity and full-text search; seed data includes embeddings

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared frontend components used by multiple user stories

- [ ] T006 Create PropertyTable component (wraps EntityDataGrid with entity-type-aware columns for schema properties and valueset members) in frontend/components/PropertyTable.tsx
- [ ] T007 Fix case-insensitive lexical sorting in EntityDataGrid — sort comparator uses localeCompare instead of default ASCII in frontend/components/EntityDataGrid.tsx

**Checkpoint**: Foundation ready — user story implementation can begin

---

## Phase 3: User Story 1 — Rich Property Tables & Entity Display (Priority: P1) 🎯 MVP

**Goal**: Property/member tables display interactive entity chips with type, unit, source, and hover popovers

**Independent Test**: Open any schema detail page → properties show EntityTag chips identical to element browse grid, including unit column

- [ ] T008 [US1] Replace ad-hoc property table in schema detail page with PropertyTable component in frontend/app/schemas/[sha256]/page.tsx
- [ ] T009 [US1] Replace ad-hoc member table in valueset detail page with PropertyTable component in frontend/app/valuesets/[sha256]/page.tsx
- [ ] T010 [US1] Add Unit column to element browse grid in frontend/app/elements/page.tsx
- [ ] T011 [US1] Add "unresolved" indicator styling to EntityTag for properties that cannot be resolved — monospace name with subtle badge in frontend/components/EntityTag.tsx
- [ ] T012 [US1] Verify all property tables render entity chips with popovers by visually reviewing schema, valueset, and element browse pages

**Checkpoint**: Property tables show rich entity chips; element browse has unit column

---

## Phase 4: User Story 3 — Modernized Layout & Reduced Whitespace (Priority: P1)

**Goal**: Denser UI with tighter spacing — 20+ rows visible at 1080p

**Independent Test**: Load element browse → 20+ rows visible without scrolling at 1080p

- [ ] T013 [P] [US3] Reduce table row height and cell padding in EntityDataGrid (48px→32px rows, p-2→p-1.5 cells) in frontend/components/EntityDataGrid.tsx
- [ ] T014 [P] [US3] Compact EntityDetailLayout — reduce section gaps (space-y-6→space-y-3), card padding (p-4→p-2), property grid to 3-column on desktop in frontend/components/EntityDetailLayout.tsx
- [ ] T015 [US3] Convert ontology annotations display to compact chips (CURIE + score + external link icon) with tooltip for full URI in frontend/components/EntityDetailLayout.tsx (depends on T014, same file)
- [ ] T016 [US3] Convert provenance display to horizontal badge strip with expandable details on click in frontend/components/EntityDetailLayout.tsx (depends on T015, same file)
- [ ] T017 [US3] Update all detail pages (elements, schemas, values, valuesets, transforms) to use compact card grid layout in frontend/app/elements/[sha256]/page.tsx, frontend/app/schemas/[sha256]/page.tsx, frontend/app/values/[sha256]/page.tsx, frontend/app/valuesets/[sha256]/page.tsx, frontend/app/transforms/[sha256]/page.tsx

**Checkpoint**: 20+ rows visible on browse pages; detail pages fit without scrolling at 1080p

---

## Phase 5: User Story 2 — Chat-First Curation Flow (Priority: P1)

**Goal**: "Suggest Change" opens chat with full entity context; chat accessible from anywhere

**Independent Test**: Click "Suggest Change" on element → chat right panel shows all fields, provenance, annotations, flags, related schemas

- [ ] T018 [US2] Build full entity context card for chat right panel — display all semantic fields, provenance with source badges, ontology annotation chips, related entities (schemas using this element, transforms), and pending curation flags in frontend/app/curation/chat/page.tsx
- [ ] T019 [US2] Support all entity types in chat right panel — type-appropriate field layouts (properties for schemas, members for valuesets, source/target for transforms) in frontend/app/curation/chat/page.tsx
- [ ] T020 [US2] Add "Chat about this" link to EntityTag popover (navigates to /curation/chat?entity={sha256}&type={entityType}) in frontend/components/EntityTag.tsx
- [ ] T020a [US2] Add row-level "Chat" action icon on browse table hover — visible on all browse pages (elements, schemas, values, valuesets, transforms) in frontend/components/EntityDataGrid.tsx
- [ ] T021 [US2] Add standalone assistant mode — when no entity param, chat starts in general-purpose mode with entity search capability in frontend/app/curation/chat/page.tsx
- [ ] T022 [US2] Add "Assistant" link under CURATION group in sidebar (navigates to /curation/chat with no entity) in frontend/components/Sidebar.tsx

**Checkpoint**: Chat reachable from any entity reference; standalone assistant works; right panel shows full entity context

---

## Phase 6: User Story 4 — Contextual Overlays & Cross-Links (Priority: P2)

**Goal**: Every entity reference is an interactive link; detail pages show cross-references

**Independent Test**: Element detail page shows "Used in Schemas" and "Transforms" sections with EntityTag links

- [ ] T023 [P] [US4] Add "Used in Schemas" section to element detail page — query schemas whose properties include this element's sha256 or provenance name in frontend/app/elements/[sha256]/page.tsx
- [ ] T024 [P] [US4] Add "Transforms" section to element detail page — query transforms where source_element or target_element matches this element in frontend/app/elements/[sha256]/page.tsx
- [ ] T025 [P] [US4] Add "Extends" parent schema link on schema detail page — clickable EntityTag linking to parent schema in frontend/app/schemas/[sha256]/page.tsx
- [ ] T026 [P] [US4] Add "Used By Elements" section to valueset detail page — query elements whose response_options reference this valueset in frontend/app/valuesets/[sha256]/page.tsx
- [ ] T027 [US4] Add GraphQL queries for cross-references: schemasUsingElement(sha256), transformsForElement(sha256), elementsUsingValueset(sha256) in backend/src/graphql/resolvers.py and backend/src/graphql/schema.py
- [ ] T028 [US4] Add corresponding frontend GraphQL queries in frontend/graphql/queries.ts
- [ ] T029 [US4] Ensure all external URIs (ontology term_uri, QUDT unit_uri) render as outbound links with external-link icon, opening in new tab — audit all detail pages

**Checkpoint**: Detail pages show bidirectional cross-references; all URIs are clickable outbound links

---

## Phase 7: User Story 7 — Global Search (Priority: P1)

**Goal**: Single search bar queries all entity types with lexical + semantic matches

**Independent Test**: Type "age" in global search → results show "age" elements (lexical) + "date_of_birth" (semantic), grouped by type

- [ ] T030 [US7] Implement search_service.py — hybrid search combining tsvector full-text (lexical) and pgvector cosine similarity (semantic), deduplication, scoring in backend/src/services/search_service.py
- [ ] T031 [US7] Add SearchResult and SearchResultConnection Strawberry types in backend/src/graphql/types.py
- [ ] T032 [US7] Add globalSearch resolver in backend/src/graphql/resolvers.py wiring to search_service
- [ ] T033 [US7] Add globalSearch query to GraphQL schema in backend/src/graphql/schema.py
- [ ] T034 [US7] Add GLOBAL_SEARCH GraphQL query in frontend/graphql/queries.ts
- [ ] T035 [US7] Create GlobalSearch component — search bar in sidebar with results dropdown grouped by entity type, match type indicators, entity tag chips, and "Chat about this" action per result in frontend/components/GlobalSearch.tsx
- [ ] T036 [US7] Integrate GlobalSearch into Sidebar layout in frontend/components/Sidebar.tsx
- [ ] T037 [US7] Verify search returns both lexical and semantic results for query "age" with results <1s

**Checkpoint**: Global search accessible from every page; returns ranked lexical + semantic results

---

## Phase 8: User Story 5 — Link Health Monitoring (Priority: P2)

**Goal**: Background checker verifies external URI domains; status page shows health dashboard

**Independent Test**: Open /status → see domain health table with green/red indicators

- [ ] T038 [US5] Add LinkHealthCheck model to backend/src/db/models.py
- [ ] T039 [US5] Implement link_checker.py background task — extract distinct domains and ontology base-URI prefixes, HEAD request with redirect following, upsert results, create curation flags for failures in backend/src/services/link_checker.py
- [ ] T040 [US5] Add LinkHealthCheck and LinkHealthDashboard Strawberry types in backend/src/graphql/types.py
- [ ] T041 [US5] Add linkHealthStatus and linkHealthChecks resolvers in backend/src/graphql/resolvers.py
- [ ] T042 [US5] Wire link health queries into GraphQL schema in backend/src/graphql/schema.py
- [ ] T043 [US5] Schedule background task to run on startup and daily thereafter in backend/src/main.py
- [ ] T044 [US5] Add LINK_HEALTH_STATUS and LINK_HEALTH_CHECKS GraphQL queries in frontend/graphql/queries.ts
- [ ] T045 [US5] Create status page with domain health dashboard, ontology prefix redirect tracking, and drill-down to affected entities in frontend/app/status/page.tsx
- [ ] T046 [US5] Add "Status" link to sidebar under PIPELINE group in frontend/components/Sidebar.tsx

**Checkpoint**: Status page shows domain health; broken domains generate curation flags

---

## Phase 9: User Story 6 — Transform Validation (Priority: P2)

**Goal**: Array→singleton transforms rejected unless structural annotation exists

**Independent Test**: Run transform pipeline → no array→singleton transforms without structural_type

- [ ] T047 [P] [US6] Add structural_type optional field to SemanticIdentity model (NOT in hash) in library/src/undata_library/models.py
- [ ] T048 [US6] Add array→singleton validation rule in transform pipeline — reject unless source element has structural_type annotation in library/src/undata_library/transform.py
- [ ] T049 [US6] Display structural_type on transform detail page when present in frontend/app/transforms/[sha256]/page.tsx

**Checkpoint**: Transform pipeline enforces array→singleton validation; UI shows structural type

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Final integration, verification, cleanup

- [ ] T050 Regenerate seed data with embeddings by re-running pipeline and copying to backend/seed/
- [ ] T051 Run quickstart.md validation — verify all visual checks and GraphQL queries work
- [ ] T052 Verify mobile responsiveness — tables switch to card layouts, split panels stack vertically
- [ ] T053 [P] Audit all detail pages for consistent dense layout, outbound links, and cross-reference sections
- [ ] T053a [P] Audit EntityDiff, ChatPanel, and EvidencePanel for non-interactive entity refs — ensure all sha256 references render as EntityTag links with popovers (FR-005) in frontend/components/EntityDiff.tsx, frontend/components/ChatPanel.tsx, frontend/components/EvidencePanel.tsx
- [ ] T054 [P] Verify case-insensitive sorting works on all browse pages and property tables

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Setup (T001-T005)
- **US1 (Phase 3)**: Depends on Foundational (T006-T007)
- **US3 (Phase 4)**: Depends on Foundational — can run in parallel with US1
- **US2 (Phase 5)**: Depends on US1 and US3 (needs rich tables and dense layout in place)
- **US4 (Phase 6)**: Depends on US1 (needs EntityTag and PropertyTable working)
- **US7 (Phase 7)**: Depends on Setup (T001-T005 for search infra) — can run in parallel with US1/US3
- **US5 (Phase 8)**: Independent of other stories — depends only on Setup
- **US6 (Phase 9)**: Independent — library-only change + minor frontend
- **Polish (Phase 10)**: Depends on all stories complete

### User Story Dependencies

- **US1 (Rich Tables)**: Foundation only — MVP starting point
- **US3 (Dense Layout)**: Foundation only — can parallel with US1
- **US2 (Chat-First)**: Benefits from US1+US3 being done (rich context display)
- **US4 (Cross-Links)**: Benefits from US1 (EntityTag enhancements)
- **US7 (Search)**: Setup phase only — backend-heavy, can parallel with frontend stories
- **US5 (Link Health)**: Fully independent — backend-only + one frontend page
- **US6 (Transform Validation)**: Fully independent — library + one frontend update

### Parallel Opportunities

- T013, T014 (US3 layout changes) — different components, run in parallel; T015→T016 sequential (same file as T014)
- T023, T024, T025, T026 (US4 cross-references) — all different detail pages, run in parallel
- T047, T048 (US6) — model change + validation rule in different files
- US7 backend (T030-T033) can run in parallel with US1/US3/US4 frontend work

---

## Implementation Strategy

### MVP First (US1 + US3)

1. Complete Phase 1: Setup (search infra, embeddings)
2. Complete Phase 2: Foundational (PropertyTable, sorting fix)
3. Complete Phase 3: US1 (rich property tables)
4. Complete Phase 4: US3 (dense layout)
5. **STOP and VALIDATE**: Property tables show chips, 20+ rows visible, unit column works

### Incremental Delivery

1. Setup + Foundational → infrastructure ready
2. US1 + US3 → visual quality baseline (MVP)
3. US2 → chat-first curation flow
4. US7 → global search
5. US4 → cross-links and overlays
6. US5 + US6 → link health + transform validation
7. Polish → final verification

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Each user story is independently testable at its checkpoint
- Commit after each task or logical group
- Seed data must be regenerated with embeddings before search works (T050)
