# Implementation Plan: AI-Assisted Curation Interface

**Branch**: `034-curation-interface` | **Date**: 2026-03-28 | **Spec**: [spec.md](spec.md)

## Summary

Build a curator interface with LLM-powered chat for editing entities. Split-panel layout (chat + diff viewer), structured LLM tool calls for entity CRUD and pipeline triggers, field-level validation, diff preview before commit. Inspired by dandi-medit.

## Technical Context

**Language/Version**: TypeScript 5.x (frontend) + Python 3.14 (backend)
**Primary Dependencies**: litellm (LLM proxy), SSE for streaming, existing GraphQL API
**Testing**: Playwright E2E, backend API tests
**Constraints**: LLM tools must use backend for DB access. All changes require curator approval.

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | Split-panel is a simple flexbox. LLM tools reuse existing backend services. |
| II. TDD | PASS | Tool call tests before implementation. |
| III. API-First Design | PASS | LLM tools defined as contract in contracts/llm-tools.md. |
| IV. Observability | PASS | All LLM calls logged. Tool execution traced. |
| V. No Deprecation | PASS | New pages/components, no removal. |
| VI. Environment Isolation | PASS | LLM via litellm (existing). |
| VII. Developer Experience | PASS | Works with local ollama or OpenAI key. |
| CI Green Before Merge | PASS | Playwright tests for curation flow. |

## Project Structure

```text
backend/src/
├── services/
│   └── chat_service.py           # NEW: LLM chat with tool execution
├── graphql/
│   ├── schema.py                 # UPDATE: entity update mutations + chatCompletion
│   └── resolvers.py              # UPDATE: update resolvers
└── tools/
    ├── __init__.py               # NEW: tool registry
    ├── entity_tools.py           # NEW: propose_change, create, delete, fetch
    ├── ontology_tools.py         # NEW: lookup_ontology_term
    └── pipeline_tools.py         # NEW: trigger_ingestion

frontend/
├── app/
│   └── curation/
│       ├── page.tsx              # UPDATE: enhanced flag review
│       └── chat/
│           └── page.tsx          # NEW: split-panel curation chat
├── components/
│   ├── SplitPanel.tsx            # NEW: resizable split layout
│   ├── ChatPanel.tsx             # NEW: LLM chat with message rendering
│   ├── EntityEditor.tsx          # NEW: editable entity fields with validation
│   ├── EntityDiff.tsx            # NEW: side-by-side diff view
│   └── PendingChanges.tsx        # NEW: accumulated changes + apply/discard
└── lib/
    └── chat-api.ts               # NEW: SSE streaming chat client
```

## Implementation Approach

### Phase 1: Backend — Entity Update Mutations + Chat Endpoint
1. Add updateElement/Schema/Value/ValueSet mutations
2. Create chat_service.py — litellm integration with tool execution loop
3. Create tool definitions (entity CRUD, ontology lookup, pipeline trigger)
4. Add /api/chat SSE endpoint
5. Backend tests for mutations and tool execution

### Phase 2: Frontend — Split Panel + Entity Editor
1. Create SplitPanel.tsx (resizable divider)
2. Create EntityEditor.tsx (editable fields, validation, diff)
3. Create EntityDiff.tsx (color-coded field comparison)
4. Create PendingChanges.tsx (accumulated changes sidebar)

### Phase 3: Frontend — Chat Panel + LLM Integration
1. Create chat-api.ts (SSE streaming client)
2. Create ChatPanel.tsx (message list, input, streaming response)
3. Wire tool call results to EntityEditor (propose_change → diff)
4. Create /curation/chat page with SplitPanel layout

### Phase 4: Enhanced Curation Queue
1. Update curation page — load full entity context for each flag
2. Add "Edit Entity" button → opens EntityEditor
3. Add "Open in Chat" button → navigates to chat with entity pre-loaded

### Phase 5: Chat-Driven Ingestion + Polish
1. Wire trigger_ingestion tool to pipeline service
2. Show staged entities for review after ingestion
3. Playwright tests for full curation flow
4. CI green
