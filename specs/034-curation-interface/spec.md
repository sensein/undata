# Feature Specification: AI-Assisted Curation Interface

**Feature Branch**: `034-curation-interface`
**Created**: 2026-03-28
**Status**: Draft
**Input**: Build a curator interface with LLM-powered chat for editing entities, split-panel layout (chat + diff viewer), and a complete curation workflow — inspired by dandi-medit's pattern of AI-proposed changes with human review.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Curation Flag Review with Full Evidence (Priority: P1)

As a curator reviewing a flag, I need to see the complete context of why the flag was created — the entity being reviewed, its current state, the reason for the flag, match candidates with scores, and any LLM verification — so I can make an informed decision.

**Why this priority**: The current evidence panel shows "No evidence data available" for most flags. Without context, curators can't review effectively.

**Independent Test**: Open a curation flag → see the flagged entity's full details, the reason for the flag, candidate matches if available, and a clear explanation of what needs review.

**Acceptance Scenarios**:

1. **Given** a low_confidence flag, **When** a curator expands it, **Then** the review panel shows: the flagged entity's current fields (data_type, unit, description, provenance), the reason text, the ontology match candidates with scores, and the recommended action.
2. **Given** a flag with context containing `reason`, **When** the evidence panel renders, **Then** the reason is displayed prominently — not "No evidence data available."
3. **Given** a flag for an entity with ontology annotations, **When** the review panel loads, **Then** the current annotations are shown alongside the proposed/missing annotations for comparison.

---

### User Story 2 — Entity Editor Panel (Priority: P1)

As a curator, I need to edit any field of an entity (data_type, unit, description, ontology_annotations) with validation, so I can correct or improve entity metadata directly.

**Why this priority**: Resolving a flag often requires changing entity fields. Without an editor, curators can only approve/reject — they can't fix the underlying issue.

**Independent Test**: Open an entity from a flag → edit the unit field → see the change validated → save.

**Acceptance Scenarios**:

1. **Given** an entity detail view, **When** a curator clicks "Edit", **Then** a right panel opens showing all editable fields with the current values pre-populated.
2. **Given** the edit panel, **When** a curator changes a field value, **Then** the change is validated in real-time (e.g., data_type must be a valid enum, ontology URIs must be resolvable).
3. **Given** pending edits, **When** the curator reviews, **Then** a diff view shows the original and modified values side-by-side with additions in green and removals in red.
4. **Given** validated edits, **When** the curator clicks "Save", **Then** the entity is updated via the API and the change is recorded with the curator's identity.

---

### User Story 3 — LLM Chat Assistant for Curation (Priority: P1)

As a curator, I need a chat interface where I can ask an LLM to suggest improvements to an entity — better ontology annotations, corrected units, improved descriptions — and see its proposals as reviewable diffs.

**Why this priority**: LLM assistance dramatically speeds up curation. The dandi-medit pattern proves this works: curators review AI proposals rather than making every change manually.

**Independent Test**: Open an entity → type "suggest a better ontology annotation for this element" → LLM proposes a change → diff appears in the edit panel.

**Acceptance Scenarios**:

1. **Given** the chat panel with an entity loaded, **When** a curator asks "what ontology term best matches this element?", **Then** the LLM searches the ontology store and proposes an annotation with URI, label, and confidence.
2. **Given** an LLM proposal, **When** the proposal is displayed, **Then** it appears as a pending diff in the edit panel — not applied until the curator approves.
3. **Given** the LLM has access to the ontology store, **When** it proposes an ontology annotation, **Then** the URI is validated against the store (not hallucinated).
4. **Given** a batch of related flags, **When** a curator asks "fix units for all MRI elements", **Then** the LLM proposes changes for multiple entities that the curator can review and apply.

---

### User Story 4 — Split-Panel Layout (Priority: P1)

As a curator, I need a split-panel view — chat on the left, entity editor/diff on the right — so I can interact with the LLM and see entity changes simultaneously.

**Why this priority**: The split-panel is the core UX pattern from dandi-medit. It enables conversational curation where the curator and AI collaborate on the right entity state.

**Independent Test**: Open the curation interface → see chat panel (left) and entity panel (right) side-by-side with a resizable divider.

**Acceptance Scenarios**:

1. **Given** the curation view, **When** it loads, **Then** a resizable split-panel shows chat on the left and entity details/editor on the right.
2. **Given** the split-panel, **When** a user drags the divider, **Then** the panels resize proportionally (25%-75% range).
3. **Given** a mobile viewport, **When** the view loads, **Then** the panels stack vertically with a tab toggle between chat and editor.

---

### User Story 5 — Entity CRUD via Chat (Priority: P2)

As a curator, I need to be able to add new entities, update existing ones, and mark entities for deletion through the chat interface — so the entire curation workflow is accessible through conversation.

**Why this priority**: Beyond editing individual fields, curators need to create new entities (e.g., split a multi-unit element), merge duplicates, or flag entities for removal. P2 because the basic edit flow (US2+US3) must work first.

**Independent Test**: Type "create a new element for age in months with unit=months" → LLM creates the entity → curator reviews and approves.

**Acceptance Scenarios**:

1. **Given** the chat interface, **When** a curator says "create a new element", **Then** the LLM generates a valid entity with all required fields and shows it as a diff (new entity).
2. **Given** an existing entity, **When** a curator says "merge this with element X", **Then** the LLM proposes a merged entity combining provenance from both and shows the diff.
3. **Given** an entity, **When** a curator says "delete this entity", **Then** the system marks it for deletion with the curator's justification recorded.

---

### Edge Cases

- What happens when the LLM proposes an invalid change (e.g., setting data_type to "banana")? The change is rejected with a validation error shown in the chat.
- What happens when two curators edit the same entity simultaneously? Optimistic locking — the second save fails with a conflict message showing the other curator's changes.
- What happens when the LLM hallucinates an ontology URI? The `lookup_ontology_term` tool validates against the store before proposing.
- What happens when the user's session expires during a long curation session? Unsaved edits are preserved in browser state; the user is prompted to re-authenticate.
- What happens when the chat context gets too long? Conversation can be summarized to free context window.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Curation flags MUST display the flagged entity's complete current state alongside the flag reason and any match candidates.
- **FR-002**: Curators MUST be able to edit any field of an entity (data_type, unit, description, ontology_annotations, provenance) with real-time validation.
- **FR-003**: Entity edits MUST be shown as color-coded diffs (green=added, red=removed) before committing.
- **FR-004**: The system MUST provide an LLM chat interface where curators can request entity improvements.
- **FR-005**: The LLM MUST use structured tool calls (not free-form text) to propose entity changes, with each proposal validated against the entity schema.
- **FR-006**: The LLM MUST have access to the ontology store for validated term lookups (no hallucinated URIs).
- **FR-007**: The curation interface MUST use a resizable split-panel layout (chat left, editor right).
- **FR-008**: All entity modifications MUST record the curator's identity and the modification reason.
- **FR-009**: The system MUST support batch operations — a curator can ask the LLM to propose changes across multiple entities.
- **FR-010**: Full CRUD (create, read, update, delete) for entities MUST be available through the chat interface. Update includes modifying any field conversationally (e.g., "change the unit of age to months").
- **FR-011**: Every LLM-proposed change MUST be reviewable as a diff before being applied.
- **FR-012**: The interface MUST work for all entity types: elements, schemas, values, valuesets.
- **FR-013**: The chat interface MUST support triggering pipeline ingestion on new sources — a curator can provide a source URL and reference an existing adapter pattern (e.g., "ingest this using the BIDS adapter"). The LLM calls the pipeline and shows ingestion results for review.
- **FR-014**: Ingestion results from chat-triggered pipeline runs MUST be reviewable before committing to the registry — showing new entities, modified entities, and conflicts.

### Key Entities

- **CurationSession**: A conversation between a curator and the LLM about one or more entities, with accumulated pending changes.
- **PendingChange**: A proposed modification to an entity field, shown as a diff, not yet committed.
- **EntityDiff**: Visual representation of changes (original vs proposed) for curator review.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Curators can resolve a curation flag by editing entity fields within the curation interface in under 2 minutes.
- **SC-002**: LLM-proposed ontology annotations are validated against the ontology store — zero hallucinated URIs accepted.
- **SC-003**: All entity edits show a diff preview before committing.
- **SC-004**: The split-panel layout works on desktop (1200px+) and mobile (375px).
- **SC-005**: Curators can complete a batch review of 5 related flags in under 10 minutes using chat commands.
- **SC-006**: Every committed change records the curator's identity and is visible in the activity feed.

## Clarifications

### Session 2026-03-28

- Q: Does CRUD via chat include update/modification explicitly? → A: Yes — chat supports full CRUD: create new entities, read/inspect existing ones, update/modify any field conversationally (e.g., "change the unit of age to months"), and delete/deprecate entities. All with diff preview before commit.
- Q: Can the chat trigger new ingestion flows? → A: Yes — a curator can point the chat to a new source and say "ingest this using the BIDS adapter pattern" or "run the pipeline on this source." The LLM calls `trigger_ingestion(source_url, adapter_pattern)` which runs the pipeline and shows results for review. Existing adapter patterns serve as templates for new sources.

## Scope Boundaries

### In Scope

- Curation flag review with full entity context and evidence display
- Entity field editor with validation and diff preview
- LLM chat assistant with structured tool calls for entity modifications
- Ontology term lookup tool for the LLM
- Split-panel layout (chat + editor) with resizable divider
- Entity CRUD operations via chat (create, read, **update**, delete)
- **Chat-driven ingestion** — trigger pipeline runs on new sources using existing adapter patterns as templates
- Batch curation operations
- Change attribution (who changed what)

### Out of Scope

- Curation proposal sharing/link system (future feature)
- Custom LLM model fine-tuning
- Offline curation (requires backend connection)
- Automated curation without human review (all changes require curator approval)

## Assumptions

- The backend GraphQL API supports entity update mutations (may need new mutations)
- LLM access via litellm/OpenRouter or local ollama (existing infrastructure from enrichment)
- The ontology store is queryable from the frontend via a backend endpoint
- The existing auth system provides curator identity for change attribution
- dandi-medit's client-side LLM pattern is adaptable to our server-proxied model

## Dependencies

- Feature 031 (CivicDB UI) — provides detail page layout and entity display components
- Feature 032 (Authentication) — provides curator identity and role-based access
- Feature 029 (Backend service) — provides GraphQL API for entity operations
- dandi-medit (https://github.com/dandi/dandi-medit) — UX/interaction pattern reference
