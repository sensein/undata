# Research: AI-Assisted Curation Interface

## R1: LLM Integration Architecture

**Decision**: Server-side LLM proxy — frontend sends chat messages to backend `/api/chat` endpoint, backend calls LLM via litellm (existing infrastructure), executes tool calls against the database, and streams responses back via SSE.

**Rationale**: Backend proxy keeps API keys server-side, enables tool calls against the database (entity CRUD, pipeline triggers, ontology lookups), and works with both OpenAI and local ollama. The dandi-medit client-side pattern doesn't work for us because our tools need database access.

**Alternatives**: Client-side LLM (dandi-medit pattern) — rejected because tools need backend access. WebSocket — more complex than SSE for one-directional streaming.

## R2: LLM Tool Definitions

**Decision**: 6 tools available to the LLM:

1. `propose_entity_change(entity_type, sha256, field, value)` — proposes a field change, validates against schema, returns diff
2. `create_entity(entity_type, data)` — proposes a new entity, validates, returns preview
3. `delete_entity(entity_type, sha256, reason)` — proposes deletion, returns confirmation
4. `lookup_ontology_term(query, ontology?)` — searches ontology store, returns validated URIs
5. `fetch_entity(entity_type, sha256)` — loads entity for context
6. `trigger_ingestion(source_url, adapter_pattern)` — triggers pipeline run, returns results summary

All tools return structured results. Proposed changes are accumulated as PendingChanges, not applied immediately.

## R3: Split-Panel Component

**Decision**: Use a simple CSS flexbox with a draggable divider. Left panel (chat): min 25%, max 75%. Right panel (editor): fills remaining space. On mobile (<768px): full-width tabs (Chat/Editor toggle).

**Rationale**: No need for a library — a 50-line React component handles the resize. dandi-medit uses this exact pattern.

## R4: Diff Rendering

**Decision**: Compute diffs client-side by comparing original entity dict with modified dict. Render as side-by-side or inline diff with green (added) / red (removed) highlighting using Tailwind classes.

**Rationale**: jsondiffpatch (used by dandi-medit) is an option but adds a dependency. For our structured entities with known fields, simple field-by-field comparison is sufficient and avoids the dep.

## R5: Backend Mutations Needed

**Decision**: Add these GraphQL mutations:
- `updateElement(sha256, input)` — updates element fields
- `updateSchema(sha256, input)` — updates schema fields
- `updateValue(sha256, input)` — updates value fields
- `updateValueSet(sha256, input)` — updates valueset fields
- `chatCompletion(messages, entityContext?)` — proxied LLM chat with tool execution

## R6: Chat-Driven Ingestion

**Decision**: The `trigger_ingestion` tool calls the existing library pipeline functions via the backend service layer (same as `triggerPipelineRun` mutation). Results are staged — the curator reviews new/modified entities before committing. The adapter pattern is specified by name (e.g., "bids", "nwb") or by referencing an existing adapter's configuration.
