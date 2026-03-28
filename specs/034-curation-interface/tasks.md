# Tasks: AI-Assisted Curation Interface

**Input**: Design documents from `/specs/034-curation-interface/`
**Prerequisites**: plan.md, spec.md (with clarifications), research.md, contracts/llm-tools.md, quickstart.md

**Tests**: Included — backend tool tests + Playwright E2E.

**Organization**: 5 user stories. US1 (flag review) is quick fix. US2 (editor) + US3 (LLM chat) + US4 (split panel) are tightly coupled P1s built together. US5 (CRUD + ingestion via chat) is P2.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: Which user story (US1–US5)

## Phase 1: Setup

**Purpose**: Backend tools package, LLM dependencies, frontend structure

- [ ] T001 Create `backend/src/tools/` package with `__init__.py`
- [ ] T002 Add `litellm>=1.0` to `backend/pyproject.toml` if not present (for LLM proxy)
- [ ] T003 Create `frontend/app/curation/chat/` directory for the split-panel chat page
- [ ] T004 Add `OPENAI_API_KEY` or `OLLAMA_HOST` to backend `docker-compose.yml` environment (from .env)

**Checkpoint**: Tool package exists, LLM deps ready

---

## Phase 2: Foundational — Backend Entity Update Mutations + Chat Endpoint

**Purpose**: Backend support for entity editing and LLM chat — BLOCKS all frontend work

**⚠️ CRITICAL**: Frontend editor and chat depend on these mutations

### Tests

- [ ] T005 Write `backend/tests/test_entity_mutations.py` — test updateElement mutation: change unit field, verify updated value, verify old value preserved in diff response. Test validation: reject invalid data_type

### Implementation

- [ ] T006 Add `updateElement`, `updateSchema`, `updateValue`, `updateValueSet` input types to `backend/src/graphql/types.py` — UpdateElementInput with optional fields (dataType, unit, description, ontologyAnnotations, etc.)
- [ ] T007 Implement update resolvers in `backend/src/graphql/resolvers.py` — `resolve_update_element(session, sha256, input)` fetches entity, applies changes, returns updated entity. Records curator identity.
- [ ] T008 Wire update mutations in `backend/src/graphql/schema.py` — `updateElement(sha256, input)`, `updateSchema`, `updateValue`, `updateValueSet`. All require curator auth.
- [ ] T009 Create `backend/src/tools/entity_tools.py` — implement `propose_entity_change()`, `create_entity()`, `delete_entity()`, `fetch_entity()` as Python functions callable by the LLM tool loop. Each validates inputs and returns structured results.
- [ ] T010 [P] Create `backend/src/tools/ontology_tools.py` — implement `lookup_ontology_term(query, ontology, limit)` using OntologyStore.search_terms(). Returns validated URIs with labels.
- [ ] T011 [P] Create `backend/src/tools/pipeline_tools.py` — implement `trigger_ingestion(source_url, adapter_pattern)` calling library pipeline functions. Returns stats.
- [ ] T012 Create `backend/src/services/chat_service.py` — LLM chat service: accepts messages + entity context, calls litellm.completion() with tool definitions from contracts/llm-tools.md, executes tool calls in a loop, streams responses via SSE. Uses existing litellm/ollama infrastructure.
- [ ] T013 Add `/api/chat` SSE endpoint to `backend/src/main.py` — POST with {messages, entityContext}, streams chat response chunks. Requires auth (curator role).
- [ ] T014 Run entity mutation tests — all must pass

**Checkpoint**: Entity updates work via GraphQL. Chat endpoint streams LLM responses with tool execution.

---

## Phase 3: User Story 1 — Enhanced Flag Review (Priority: P1)

**Goal**: Curation flags show full entity context, reason, and evidence.

**Independent Test**: Expand a flag → see entity fields + reason text + match candidates.

- [ ] T015 [US1] Update `frontend/components/EvidencePanel.tsx` — always show the flagged entity's key fields (data_type, unit, description, source) at the top of the panel, loaded via a separate GraphQL query using entity_ref
- [ ] T016 [US1] Update `frontend/app/curation/page.tsx` — add "Edit Entity" button on each flag card (opens EntityEditor) and "Open in Chat" button (navigates to /curation/chat?entity=sha256)
- [ ] T017 [US1] Verify: expand a flag → entity context visible, reason displayed, "Edit Entity" and "Open in Chat" buttons present

**Checkpoint**: Flag review shows full context. Buttons link to editor and chat.

---

## Phase 4: User Stories 2+4 — Entity Editor + Split Panel (Priority: P1)

**Goal**: Editable entity fields in a right panel with validation and diff preview.

**Independent Test**: Open entity from flag → edit unit → see diff → save.

- [ ] T018 [US4] Create `frontend/components/SplitPanel.tsx` — resizable flexbox layout: left panel (min 25%) + draggable divider (6px) + right panel. Mobile: full-width with tab toggle (Chat/Editor). Props: leftContent, rightContent.
- [ ] T019 [US2] Create `frontend/components/EntityEditor.tsx` — form with all entity fields pre-populated from current values. Fields: data_type (select), unit (text), description (textarea), ontology_annotations (list with add/remove). Real-time validation: data_type must be valid enum, unit validated via QUDT if available. Shows save/discard buttons.
- [ ] T020 [US2] Create `frontend/components/EntityDiff.tsx` — field-by-field comparison of original vs modified entity. Green background for added/changed fields, red strikethrough for removed values. Props: original (dict), modified (dict).
- [ ] T021 [US2] Create `frontend/components/PendingChanges.tsx` — sidebar showing accumulated changes: list of {entity_ref, field, old_value, new_value}. "Apply All" and "Discard All" buttons. Individual change revert.
- [ ] T022 [US2] Wire EntityEditor save to `updateElement` GraphQL mutation — on save, call mutation with changed fields, show success/error, refresh entity data.
- [ ] T023 [US4] Create `frontend/app/curation/chat/page.tsx` — split-panel page: ChatPanel (left) + EntityEditor/EntityDiff (right). Reads `?entity=sha256` from URL to pre-load entity. Shows PendingChanges.
- [ ] T024 [US2] Verify: open entity → edit unit → diff shows change → save → entity updated in database

**Checkpoint**: Entity editor works with validation + diff. Split-panel layout functional.

---

## Phase 5: User Story 3 — LLM Chat Assistant (Priority: P1)

**Goal**: Chat with LLM that proposes entity changes as reviewable diffs.

**Independent Test**: Type "suggest better ontology annotation" → LLM proposes → diff appears.

- [ ] T025 [US3] Create `frontend/lib/chat-api.ts` — SSE client for `/api/chat`. Sends messages + entity context, receives streamed response chunks. Handles tool_call events (display pending changes in EntityDiff).
- [ ] T026 [US3] Create `frontend/components/ChatPanel.tsx` — message list (user + assistant messages), text input with send button, streaming response rendering (markdown), tool call indicator ("Searching ontology..." / "Proposing change..."). Shows entity context badge at top.
- [ ] T027 [US3] Wire ChatPanel to EntityEditor — when LLM calls `propose_entity_change`, the result appears as a pending diff in the right panel. Curator can "Apply" or "Discard" each proposal.
- [ ] T028 [US3] Wire ChatPanel to PendingChanges — accumulated proposals shown in PendingChanges sidebar. "Apply All" commits all via update mutations.
- [ ] T029 [US3] Create system prompt in `backend/src/services/chat_service.py` — includes: entity context (current fields), available tools, instructions (use lookup_ontology_term, propose changes via tools, never output raw JSON)
- [ ] T030 [US3] Verify: open chat with entity → ask for ontology suggestion → LLM calls lookup_ontology_term → proposes annotation → diff appears → apply → entity updated

**Checkpoint**: Full LLM chat → diff → apply flow works end-to-end.

---

## Phase 6: User Story 5 — CRUD + Ingestion via Chat (Priority: P2)

**Goal**: Create, update, delete entities + trigger ingestion through conversation.

**Independent Test**: "Create a new element for age in months" → LLM creates → curator approves.

- [ ] T031 [US5] Wire `create_entity` tool — LLM calls it, result shown as new entity preview in right panel. Curator clicks "Create" to commit via GraphQL mutation.
- [ ] T032 [US5] Wire `delete_entity` tool — LLM proposes deletion with reason, confirmation dialog. Curator confirms → entity marked for deletion.
- [ ] T033 [US5] Wire `trigger_ingestion` tool — LLM triggers pipeline, shows staged results (N elements, N schemas). Curator reviews → "Commit" button writes to registry.
- [ ] T034 [US5] Add batch mode to ChatPanel — when LLM proposes changes to multiple entities, PendingChanges shows all changes grouped by entity. "Apply All" commits batch.
- [ ] T035 [US5] Verify: "create element for age_months" → preview → approve. "ingest from URL using BIDS adapter" → pipeline runs → staged entities shown.

**Checkpoint**: Full CRUD + ingestion via chat works.

---

## Phase 7: Polish + Validation

**Purpose**: Tests, CI, documentation

- [ ] T036 Write Playwright test `frontend/tests/e2e/curation-chat.spec.ts` — test: split panel loads, entity editor fields visible, chat input works, save button updates entity
- [ ] T037 Verify all existing Playwright tests (20+) still pass
- [ ] T038 Verify `pnpm exec next build` passes
- [ ] T039 Update `CLAUDE.md` with curation chat usage instructions
- [ ] T040 Push branch and verify CI is green

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies
- **Phase 2 (Backend)**: Depends on Phase 1 — BLOCKS all frontend work
- **Phase 3 (Flag Review)**: Depends on Phase 2 (entity queries)
- **Phase 4 (Editor + Split)**: Depends on Phase 2 (update mutations)
- **Phase 5 (Chat + LLM)**: Depends on Phase 2 (chat endpoint) + Phase 4 (editor components)
- **Phase 6 (CRUD + Ingestion)**: Depends on Phase 5
- **Phase 7 (Polish)**: Depends on all

### Parallel Opportunities

**Phase 2**: T009, T010, T011 — entity, ontology, pipeline tools are independent
**Phase 4**: T018, T019, T020, T021 — SplitPanel, EntityEditor, EntityDiff, PendingChanges are independent components

---

## Implementation Strategy

### MVP (Phases 1-4)

1. Backend mutations + chat endpoint + tools
2. Enhanced flag review with entity context
3. Entity editor with validation + diff + save
4. **STOP and VALIDATE**: curator can edit entity fields from curation queue

### Full Delivery

5. LLM chat with tool calls → diff → apply
6. CRUD + ingestion via chat
7. Playwright tests + CI green

---

## Notes

- LLM uses litellm (existing) — works with OpenAI, Anthropic, or local ollama
- Tool calls execute server-side (backend has DB access)
- SSE streaming for chat responses (not WebSocket — simpler)
- System prompt includes entity context so LLM knows what it's editing
- All changes via mutations — frontend never writes to DB directly
- Commit after each phase
