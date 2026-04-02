# Feature Specification: System Hardening — LLM Curation, Transforms, Sources, UI & Infrastructure

**Feature Branch**: `038-system-hardening`
**Created**: 2026-04-02
**Status**: Draft
**Input**: Address 18 outstanding tasks across search, ontology management, transforms, data sources, LLM curation, infrastructure, UI polish, pipeline enrichment, and CI.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Live LLM Curation Chat (Priority: P1)

As a curator, I need the curation chat to actually connect to an LLM that responds with entity-aware suggestions — proposing annotation improvements, unit corrections, and description enhancements — so I can curate entities through conversation rather than manual editing.

**Why this priority**: The chat UI exists but the LLM backend doesn't process messages. This is the core curation workflow.

**Independent Test**: Open chat for an element → type "suggest better annotations" → LLM responds with specific proposals referencing the entity's fields → proposals appear as reviewable diffs.

**Acceptance Scenarios**:

1. **Given** the chat page with an entity loaded, **When** a curator sends a message, **Then** the LLM receives the entity context (all fields, provenance, annotations) and responds with entity-aware suggestions.
2. **Given** the chat, **When** the LLM proposes a change (annotation, unit, description), **Then** the proposal appears as a diff in the right panel that can be approved or rejected.
3. **Given** the chat with no entity loaded (assistant mode), **When** a curator asks "find elements with missing units", **Then** the LLM searches the registry and returns relevant entities.
4. **Given** the chat, **When** an entity is first loaded, **Then** the system automatically suggests improvements based on the entity's current state (missing annotations, inferred units, description quality).

---

### User Story 2 — Name-Based Transform Generation (Priority: P1)

As a data engineer, I need the transform pipeline to detect cross-source mappings using element name similarity (not just shared ontology URIs) — so transforms between "age" in BIDS and "age" in NWB are automatically discovered even when they lack matching annotations.

**Why this priority**: Current transforms only match by shared ontology URI, producing just 15 transforms across 2191 elements. Name-based matching dramatically increases coverage.

**Independent Test**: Run transform pipeline → transforms created between BIDS "age" and NWB "age", between BIDS "sex" and DANDI "sex", etc. — based on name similarity + type compatibility.

**Acceptance Scenarios**:

1. **Given** elements sharing the same provenance name across sources (e.g., "age" in BIDS and "age" in NWB), **When** the transform pipeline runs, **Then** a transform is created with appropriate function_type (identity if same type/unit, type_conversion or unit_conversion if different).
2. **Given** the transform pipeline, **When** evaluating name-based matches, **Then** it uses a similarity threshold (embedding cosine or string similarity) to avoid false matches between unrelated elements.
3. **Given** the transform pipeline, **When** generating transforms, **Then** it supports many-to-one mappings where multiple source elements map to a single target (e.g., age + age_unit → age_in_years).

---

### User Story 3 — Additional Data Sources (Priority: P1)

As a data engineer, I need to ingest schema descriptors from OpenNeuro datasets (via datalad), the ReproSchema library, the NDA data dictionary API, and stats/mapping repositories — so the registry covers real-world dataset usage beyond the 5 specification sources.

**Why this priority**: The registry currently covers only standard specifications (BIDS, NWB, DANDI, AIND, openMINDS). Real datasets extend these with custom fields that need to be tracked.

**Independent Test**: Ingest 10 OpenNeuro datasets → new elements appear from participants.tsv and phenotype TSVs → ingest ReproSchema library → activities and items appear as schemas and elements.

**Acceptance Scenarios**:

1. **Given** the OpenNeuro adapter (already implemented), **When** ingestion runs on a dataset ID, **Then** elements are extracted from all TSV/CSV files with JSON sidecar descriptions.
2. **Given** the ReproSchema adapter (already implemented), **When** ingestion runs on the reproschema-library, **Then** activities become schemas and items become elements with response options and min/max values.
3. **Given** the NDA data dictionary API, **When** a curator provides an NDA structure short name, **Then** the system fetches the data dictionary and extracts elements with descriptions, types, and value ranges.
4. **Given** the discovery service, **When** new datasets appear on OpenNeuro or DANDI, **Then** they are automatically queued for ingestion.

---

### User Story 4 — Search with Lexical & Semantic Toggle (Priority: P2)

As a researcher, I need the search page to offer both lexical (keyword) and semantic (meaning-based) search modes — so I can find exact matches by name OR discover related concepts by meaning.

**Why this priority**: Current search is lexical only. Semantic search enables discovery of related concepts (e.g., searching "brain area" finds "brain_region" elements).

**Independent Test**: Search "brain area" in semantic mode → results include "brain_region", "cortical_area", "anatomical_region" — not just exact text matches.

**Acceptance Scenarios**:

1. **Given** the search page, **When** a user selects "Lexical" mode and searches, **Then** results are text matches (substring, prefix) on names and descriptions.
2. **Given** the search page, **When** a user selects "Semantic" mode and searches, **Then** results are embedding-similarity matches with similarity scores.
3. **Given** the search page, **When** a user selects "Both" mode (default), **Then** lexical matches appear first, followed by semantic matches with a separator.

---

### User Story 5 — Ontology Admin & NCBITaxon Filtering (Priority: P2)

As a system administrator, I need the ontology admin page to show loaded ontologies with term counts — and the NCBITaxon ontology filtered to neuroscience-relevant species only in the embedding index.

**Why this priority**: The admin page shows empty because ontologies are in pyoxigraph, not the DB. NCBITaxon's 2.7M terms dilute the embedding index.

**Independent Test**: Open /admin/ontologies → see loaded ontologies with term counts. Run enrichment → NCBITaxon matches are limited to relevant species (mouse, rat, human, macaque, zebrafish, fly, worm).

**Acceptance Scenarios**:

1. **Given** the ontology admin page, **When** it loads, **Then** it queries the ontology store (not DB) and displays loaded ontologies with name, term count, and last refresh date.
2. **Given** the NCBITaxon ontology in the embedding index, **When** the index is rebuilt, **Then** only neuroscience-relevant species and their immediate taxonomic parents are included (~100 terms, not 2.7M).

---

### User Story 6 — Server-Side Sorting & Infinite Scroll (Priority: P2)

As a researcher browsing entities, I need column sorting to fetch server-sorted data and infinite scroll to load more results automatically — so I can browse large datasets efficiently.

**Why this priority**: Client-side sorting only re-sorts the loaded page. Infinite scroll replaces the "Load more" button for smoother UX.

**Independent Test**: Click "Unit" column on elements page → all elements with units appear first (server-sorted). Scroll to bottom → next page loads automatically.

**Acceptance Scenarios**:

1. **Given** any browse page, **When** a user clicks a column header, **Then** the system re-fetches from the server sorted by that column (not client-side re-sort of loaded page).
2. **Given** any browse page, **When** the user scrolls near the bottom, **Then** the next page loads automatically via infinite scroll.
3. **Given** server-side sorting, **When** combined with source/type filters, **Then** the sort applies to the filtered results, not all data.

---

### User Story 7 — Audit Log & Infrastructure (Priority: P3)

As a system administrator, I need every mutation (create, update, approve, reject, enrich) recorded in a PROV-O style audit log — and nightly exports with a download page for registry releases.

**Why this priority**: Audit trail is essential for reproducibility and trust. Download page enables data sharing.

**Independent Test**: Approve a curation flag → audit log records who, what, when. Visit /downloads → see latest nightly export.

**Acceptance Scenarios**:

1. **Given** any mutation (flag resolution, entity update, annotation approval), **When** it completes, **Then** an audit log entry is created with agent, activity, entity, generated entity, and timestamp.
2. **Given** the nightly export scheduler, **When** it runs, **Then** a compressed archive is produced and listed on the download page.
3. **Given** the download page, **When** a user visits it, **Then** they see available releases with version, date, entity counts, and download link.

---

### User Story 8 — CI & Pipeline Maintenance (Priority: P3)

As a developer, I need GitHub Actions updated to Node.js 24, the ontology vector index to auto-rebuild when ontologies change, and the enrichment pipeline to support LLM-assisted verification of borderline candidates.

**Why this priority**: CI maintenance and pipeline improvements for long-term quality.

**Independent Test**: Push code → CI runs without Node.js deprecation warnings. Add new ontology → vector index rebuilds automatically.

**Acceptance Scenarios**:

1. **Given** CI workflows, **When** they run, **Then** no Node.js deprecation warnings appear (actions use v5/Node.js 24).
2. **Given** a new ontology added to the store, **When** enrichment runs, **Then** the vector index includes the new ontology terms (auto-rebuild if stale).
3. **Given** elements with borderline annotation scores (0.5-0.7), **When** LLM-assisted enrichment runs, **Then** the LLM verifies candidates and promotes confirmed ones to high-confidence annotations.

---

### Edge Cases

- What happens when the LLM is unavailable (no API key, rate limited)? Chat shows a graceful error; auto-suggest is skipped; enrichment falls back to embedding-only matching.
- What happens when name-based transform matching produces too many false positives? A similarity threshold (configurable, default 0.8) filters out weak matches.
- What happens when an NDA API request fails? The adapter retries with exponential backoff; failed requests are logged and the curator is notified.
- What happens when infinite scroll loads the same page twice? The Apollo paginationMerge deduplicates by cursor.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The curation chat MUST connect to a configured LLM backend and process messages with entity context.
- **FR-002**: When an entity is loaded in the chat, the system MUST automatically suggest improvements (missing annotations, unit inference, description quality).
- **FR-003**: The transform pipeline MUST detect cross-source mappings using element name similarity in addition to shared ontology URIs.
- **FR-004**: The transform model MUST support many-to-one mappings (multiple source elements → one target).
- **FR-005**: The system MUST support ingesting from OpenNeuro (via datalad), ReproSchema library, NDA data dictionary API, and JSON field mapping repositories.
- **FR-006**: The search page MUST offer lexical, semantic, and combined search modes with a toggle.
- **FR-007**: The ontology admin page MUST display loaded ontologies from the ontology store (not only from the database).
- **FR-008**: The NCBITaxon ontology MUST be filtered to neuroscience-relevant species before inclusion in the embedding index.
- **FR-009**: All browse pages MUST support server-side column sorting (not just client-side re-sort).
- **FR-010**: All browse pages MUST use infinite scroll (auto-load on scroll near bottom).
- **FR-011**: Every mutation MUST be recorded in a PROV-O style audit log with agent, activity, entity, and timestamp.
- **FR-012**: A nightly export scheduler MUST produce compressed archives listed on a public download page.
- **FR-013**: GitHub Actions workflows MUST use Node.js 24 compatible action versions.
- **FR-014**: The ontology vector index MUST auto-rebuild when new ontologies are added or refreshed.
- **FR-015**: LLM-assisted enrichment MUST verify borderline annotation candidates (0.5-0.7 score) and promote confirmed ones.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Curators can have a real conversation with the LLM in the chat and receive entity-specific improvement suggestions within 5 seconds.
- **SC-002**: The transform pipeline produces at least 100 cross-source transforms using name-based matching (up from 15 with ontology-only matching).
- **SC-003**: At least 10 OpenNeuro datasets and the ReproSchema library are ingested as additional sources.
- **SC-004**: Semantic search returns relevant results for conceptual queries (e.g., "brain area" finds "brain_region").
- **SC-005**: The ontology admin page displays all loaded ontologies with correct term counts.
- **SC-006**: Server-side sorting on any column header produces correctly ordered results from the full dataset.
- **SC-007**: CI runs complete without Node.js deprecation warnings.
- **SC-008**: Audit log entries are created for every mutation and queryable by entity, user, and time range.

## Scope Boundaries

### In Scope

- Wire LLM chat backend to process messages with entity context
- Auto-suggest improvements on entity load in chat
- Name-based + embedding similarity transform matching
- Many-to-one transform model extension
- OpenNeuro dataset ingestion, ReproSchema, NDA API adapter
- Search mode toggle (lexical/semantic/both)
- Ontology admin page reading from pyoxigraph store
- NCBITaxon species filtering for embeddings
- Server-side sorting for all browse pages
- Infinite scroll verification and fixes
- PROV-O audit log for all mutations
- Nightly export scheduler and download page
- CI action version updates
- Ontology vector index auto-rebuild
- LLM-assisted enrichment for borderline candidates

### Out of Scope

- Custom LLM fine-tuning for the domain
- Real-time collaborative curation (multi-user simultaneous chat)
- Cross-registry federation
- Custom ontology creation

## Assumptions

- LLM access via litellm (already a dependency) with configurable model (ollama local or cloud API)
- The existing chat SSE streaming infrastructure works; only the backend message processing needs wiring
- The NDA API is publicly accessible for data dictionary queries
- OpenNeuro datasets are accessible via datalad without authentication
- The existing embedding model (all-MiniLM-L6-v2) is sufficient for semantic search and name-based transform matching

## Dependencies

- Feature 034 (Curation Interface) — provides chat UI and SSE streaming
- Feature 035 (UX Overhaul) — provides EntityDataGrid, PropertyTable, search page
- Feature 036 (Knowledge Service) — provides ontology store, adapters, LLM enrichment skills
- Feature 037 (Data Export) — provides export service for nightly scheduler
