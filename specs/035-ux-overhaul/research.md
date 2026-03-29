# Research: UX & UI Overhaul

## R1: Global Search — Lexical + Semantic

**Decision**: Use PostgreSQL tsvector for lexical (full-text) search + pgvector for semantic (embedding) similarity, combined in a single GraphQL endpoint.

**Rationale**: pgvector is already in the Docker image (pgvector/pgvector:pg16). The library already uses all-MiniLM-L6-v2 (384-dim) for ontology matching. Combining tsvector for keyword search and pgvector for embedding similarity avoids adding an external search service (Meilisearch) while leveraging existing infrastructure.

**Alternatives considered**:
- Meilisearch: mentioned in VISION.md but adds a new service dependency; overkill for <10K entities
- ILIKE-only: current approach; no semantic matching, poor for discovery
- Client-side search: embedding model too large for browser

**Key implementation details**:
- Add `embedding vector(384)` column to Element, Schema, Value, ValueSet tables
- Add `search_tsv tsvector` column generated from name+description+provenance
- Compute embeddings during import (reuse library's `_encode_texts()`)
- Hybrid scoring: lexical matches ranked first, semantic below with similarity scores
- New `globalSearch(query, limit)` GraphQL query returning union of entity types

## R2: Property Table Rich Display

**Decision**: Reuse the existing EntityDataGrid component for schema property tables and valueset member tables, replacing the current ad-hoc `<table>` implementations.

**Rationale**: The EntityDataGrid with TanStack Table already has sorting, filtering, entity tag rendering, and pagination. Property tables should use the same component with appropriate columns, not custom tables.

**Alternatives considered**:
- Custom rich tables: would duplicate EntityDataGrid functionality
- Keep current tables, add entity tags only: partial fix, doesn't give sorting/filtering

## R3: Chat Entry Points

**Decision**: Add a "Chat" action to EntityTag popovers, browse table row hover menus, and search results. Add a persistent "Assistant" link in the sidebar that opens the chat without entity context.

**Rationale**: Chat-first curation means the chat must be reachable from anywhere entities appear. The standalone assistant mode enables general questions and entity discovery within conversation.

**Key implementation details**:
- EntityTag popover: add "Chat about this" link → `/curation/chat?entity={sha256}&type={entityType}`
- Browse table: row hover shows action icons (view, chat)
- Search results: each result has a chat action
- Sidebar: "Assistant" link under CURATION group → `/curation/chat` (no entity param)
- Chat page: when no entity param, start in general mode with entity search tool

## R4: Link Health Monitoring

**Decision**: Backend background task runs daily, checking one HEAD request per distinct domain and per ontology base-URI prefix. Results stored in a dedicated table, exposed via GraphQL and a status page.

**Rationale**: Domain-level checks (~20-30 domains) are lightweight. Ontology base-URI prefixes (e.g., `http://purl.obolibrary.org/obo/NCIT_`) may redirect differently than the domain root, so they need separate checks.

**Key implementation details**:
- Extract distinct domains and ontology base-URI prefixes from all ontology_annotations across all entity tables
- Background task (asyncio scheduled, not cron) runs daily
- Store results in `link_health_checks` table
- Status page at `/status` shows domain/ontology health
- Curation flags generated for unreachable domains

## R5: Transform Validation — Array Constraints

**Decision**: Add a validation rule in the transform pipeline that rejects array→singleton transforms unless the source element has a `structural_type` annotation (e.g., "affine_matrix", "rotation_matrix").

**Rationale**: Array-typed elements often represent lists/collections, not transformable mathematical objects. A structural_type annotation explicitly marks arrays that represent specific mathematical structures.

**Key implementation details**:
- New optional field `structural_type` on SemanticIdentity (not in hash, metadata only)
- Transform validation check in `library/src/undata_library/transform.py`
- Curator can set structural_type via chat or direct edit
- Known structural types: affine_matrix, rotation_matrix, covariance_matrix, quaternion, euler_angles

## R6: Dense UI Layout

**Decision**: Reduce table row height from 48px→32px, card padding from p-4→p-2, section gaps from space-y-6→space-y-3. Use compact chip display for ontology annotations and horizontal badge strips for provenance.

**Rationale**: Current layout shows ~12 rows at 1080p. Target is 20+. Reducing whitespace by 40% achieves this without sacrificing readability.

**Alternatives considered**:
- Virtual scrolling: adds complexity; unnecessary at <10K entities
- Pagination instead of density: hides data, worse for scanning
