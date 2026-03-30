# Feature Specification: Knowledge Service — Ontologies, Sources & Enrichment

**Feature Branch**: `036-knowledge-service`
**Created**: 2026-03-30
**Status**: Draft
**Input**: Expand the ontology store with domain-specific ontologies (HoMBA, NIDM, DICOM, RadLex), add new data sources (OpenNeuro, data repositories with accessible metadata descriptors), and build a review/enrichment workflow to improve existing elements and create new versions.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Domain-Specific Ontology Integration (Priority: P1)

As a neuroscience researcher, I need the ontology store to include brain anatomy (HoMBA), neuroimaging data descriptors (NIDM), medical imaging terms (DICOM), and radiology vocabulary (RadLex) — so that element enrichment produces relevant, domain-specific annotations instead of only generic biomedical terms.

**Why this priority**: The current ontology store (NCIT, PATO, HP, EDAM, TMN) only enriches 10% of elements. Adding domain-specific ontologies is the single highest-impact improvement for annotation coverage.

**Independent Test**: Run enrichment on BIDS elements → "EchoTime" gets annotated with DICOM tag (0018,0081) and NIDM term; "brain_region" gets HoMBA annotation; "MagneticFieldStrength" gets RadLex term.

**Acceptance Scenarios**:

1. **Given** the ontology store, **When** refreshed with the new sources, **Then** it includes terms from HoMBA (Harmonized Ontology of Mammalian Brain Anatomy, from https://github.com/Cellular-Semantics/harmonized_ontology_of_mammalian_brain_anatomy_ontology), NIDM (Neuroimaging Data Model), DICOM data element dictionary, and RadLex (Radiology Lexicon).
2. **Given** an element "EchoTime" from BIDS, **When** enrichment runs with the expanded store, **Then** it receives ontology annotations from DICOM (tag 0018,0081 "Echo Time") and/or NIDM with score > 0.8.
3. **Given** an element "brain_region", **When** enrichment runs, **Then** it receives a HoMBA annotation linking to the brain anatomy hierarchy.
4. **Given** the enrichment pipeline, **When** run on all BIDS+NWB+DANDI elements with the expanded ontology store, **Then** at least 40% of elements receive ontology annotations (up from 10%).

---

### User Story 2 — OpenNeuro & Repository Data Sources (Priority: P1)

As a data engineer, I need to ingest schema descriptors from OpenNeuro datasets and other neuroscience data repositories that expose accessible metadata — so that the registry captures how data elements are actually used across real datasets, not just the standard specifications.

**Why this priority**: Current sources (BIDS, NWB, DANDI) define schema specifications. Real datasets often extend, constrain, or deviate from specs. OpenNeuro has 800+ public datasets with `dataset_description.json` and `participants.tsv` headers that reveal actual field usage.

**Independent Test**: Run ingestion on 10 OpenNeuro datasets → elements extracted from participants.tsv columns appear in the registry with source "openneuro" and provenance linking to the specific dataset.

**Acceptance Scenarios**:

1. **Given** the OpenNeuro adapter using datalad, **When** ingestion runs on a dataset (e.g., ds000228), **Then** it scans for all CSV/TSV files (participants.tsv, phenotype/*.tsv, etc.), reads their JSON sidecars for column descriptions, and extracts elements from column headers with data types inferred from values.
2. **Given** a dataset with non-standard columns (e.g., "handedness_score", "WASI_IQ" in phenotype/behavioral.tsv), **When** ingested, **Then** each column becomes an element with data_type inferred from the column values, description from the JSON sidecar if available, and source "openneuro/{dataset_id}".
3. **Given** multiple OpenNeuro datasets using the same BIDS field (e.g., "age"), **When** ingested, **Then** the existing "age" element gains additional provenance entries from each dataset (merged by sha256 match), not duplicate elements.
4. **Given** the ReproSchema library, **When** ingested, **Then** activities and items are extracted as schemas and elements respectively, with provenance linking to the ReproSchema repository.
5. **Given** any data repository that exposes metadata via a known format (JSON-LD, CSV data dictionary, JSON Schema, JSON field mappings), **When** pointed to by a curator, **Then** the system can ingest it using the existing adapter framework.

---

### User Story 3 — Enrichment Review & Element Versioning (Priority: P1)

As a curator, I need to review enrichment results (ontology annotations, inferred units, patterns) for existing elements and either approve, reject, or refine them — creating a new version of the element when semantic changes occur (e.g., correcting the unit from "years" to "ISO8601").

**Why this priority**: Enrichment is automated and imperfect. Curators must be able to verify and improve annotations. When a semantic field changes (e.g., unit correction), the element's identity hash changes, creating a new version that must be linked to the original.

**Independent Test**: Open an element with a low-confidence annotation → reject it → propose a better annotation via chat → approve → element updated with new annotation, old annotation removed, provenance records the curation.

**Acceptance Scenarios**:

1. **Given** an element with enrichment-assigned ontology annotations, **When** a curator views the element, **Then** each annotation shows its confidence score, source model, and an approve/reject action.
2. **Given** a curator rejects an annotation, **When** they submit the rejection, **Then** the annotation is removed and a curation provenance entry is recorded (who, when, why).
3. **Given** a curator modifies a semantic field (e.g., changes unit from "years" to "months"), **When** the change is saved, **Then** a new element version is created with a new sha256, the old version is marked as superseded, and a transform is created linking old→new with function_type "curation_update".
4. **Given** the enrichment pipeline, **When** re-run on elements that have been curated, **Then** it respects curated annotations (does not overwrite approved annotations with lower-confidence automated ones).
5. **Given** the curation chat, **When** a curator asks "re-enrich this element with the new ontologies", **Then** the system re-runs enrichment for that specific element using the latest ontology store and shows the proposed new annotations as a diff.

---

### User Story 4 — Ontology Store Management (Priority: P2)

As a system administrator, I need to manage the ontology store — add new ontologies, refresh existing ones, view term counts and coverage statistics, and configure which ontologies are active for enrichment.

**Why this priority**: As the ontology store grows, administrators need visibility and control over which ontologies are loaded and their status.

**Independent Test**: Open the ontology admin page → see a table of loaded ontologies with term counts, last refresh date, and enable/disable toggle.

**Acceptance Scenarios**:

1. **Given** the ontology admin interface, **When** an admin views it, **Then** it shows each loaded ontology with: name, term count, last refresh timestamp, download source URL, and active/inactive status.
2. **Given** an admin adds a new ontology URL, **When** they submit it, **Then** the system downloads, parses (OWL/OBO/TTL), indexes terms, computes embeddings, and reports the result.
3. **Given** the ontology store, **When** refreshed, **Then** it reports: total terms, terms added/removed since last refresh, estimated enrichment coverage improvement.

---

### User Story 5 — Source Discovery & Registration (Priority: P2)

As a curator, I need to discover and register new data sources for ingestion — point the system at a repository URL, select an adapter pattern, preview the extracted entities, and approve the ingestion into the registry.

**Why this priority**: The registry must grow beyond the initial 5 sources. Curators need a self-service workflow for adding new sources without developer intervention.

**Independent Test**: Provide an OpenNeuro dataset URL → system detects it as BIDS-compatible → preview shows extracted elements/schemas → curator approves → entities ingested.

**Acceptance Scenarios**:

1. **Given** the source registration interface, **When** a curator provides a repository URL, **Then** the system auto-detects the applicable adapter (BIDS for OpenNeuro, JSON-LD for DANDI, etc.) or allows manual adapter selection.
2. **Given** a detected adapter, **When** the curator clicks "Preview", **Then** the system runs extraction in dry-run mode and shows the entities that would be created, with counts and sample entities.
3. **Given** a previewed extraction, **When** the curator approves, **Then** the full pipeline runs (extract → enrich → align → commit) and the new source appears in the registry with its provenance.
4. **Given** the chat interface, **When** a curator says "ingest this OpenNeuro dataset: ds000228", **Then** the LLM triggers the ingestion pipeline and shows results for review.

---

### User Story 6 — Automated Source Discovery & Ingestion Queue (Priority: P1)

As a system operator, I need the system to automatically monitor known repositories (OpenNeuro, DANDI Archive) for new datasets and add them to an ingestion queue — with pre-approved sources auto-ingested via their adapters and unknown sources queued for curator review — so the registry stays current without manual intervention.

**Why this priority**: The registry must grow continuously. Manual source addition doesn't scale. Pre-approved sources with existing adapters (OpenNeuro=BIDS, DANDI=dandi adapter) should be ingested automatically.

**Independent Test**: A new dataset appears on OpenNeuro → within 24 hours the system discovers it, auto-ingests via BIDS adapter, and the new elements appear in the registry with source "openneuro/{dataset_id}".

**Acceptance Scenarios**:

1. **Given** a list of approved repository endpoints (OpenNeuro API, DANDI API), **When** the discovery service runs on schedule, **Then** it queries each endpoint for new datasets since the last check and adds discovered datasets to the ingestion queue.
2. **Given** a discovered dataset from a pre-approved source with a known adapter, **When** queued, **Then** it is automatically ingested (extract → enrich → align → commit) without curator approval and the results are visible in the registry.
3. **Given** a discovered dataset from an unknown or unapproved source, **When** queued, **Then** it waits for curator review — the curator can preview extracted entities, approve, reject, or defer.
4. **Given** the ingestion queue, **When** a curator views it, **Then** they see pending, in-progress, completed, and failed ingestions with dataset metadata, adapter used, and entity counts.

---

### User Story 7 — LLM-Powered Knowledge Enhancement (Priority: P2)

As a curator, I need the system to use LLM capabilities to improve the knowledge space — suggesting better ontology mappings, disambiguating terms, inferring relationships between elements, proposing unit corrections, and generating descriptions for undocumented elements — so that automated enrichment quality approaches human-level curation.

**Why this priority**: Embedding similarity alone misses nuanced domain mappings. LLMs can reason about context (e.g., "EchoTime is a DICOM acquisition parameter measured in milliseconds") to produce higher-quality annotations than pure vector matching.

**Independent Test**: Ask the chat "suggest better annotations for EchoTime" → LLM proposes DICOM tag (0018,0081) with reasoning, plus NIDM equivalent, with confidence assessment.

**Acceptance Scenarios**:

1. **Given** an element with no or low-confidence annotations, **When** the LLM enrichment skill runs, **Then** it proposes ontology annotations with reasoning (e.g., "EchoTime maps to DICOM (0018,0081) because it represents the time between RF excitation and peak echo signal").
2. **Given** an element with ambiguous unit (inferred from description), **When** the LLM reviews it, **Then** it proposes a unit correction with justification and creates a curation flag if uncertain.
3. **Given** two elements with similar names from different sources (e.g., BIDS "age" and DANDI "age"), **When** the LLM alignment skill runs, **Then** it assesses whether they represent the same concept or different variants and proposes appropriate relationship (exactMatch, relatedMatch, or distinct).
4. **Given** an element with no description, **When** the LLM skill runs, **Then** it generates a description based on the element name, data type, unit, and source context.
5. **Given** the curation chat, **When** a curator asks "enrich all unannotated BIDS elements using LLM", **Then** the system queues batch LLM enrichment for matching elements and reports progress.

---

### Edge Cases

- What happens when an ontology URL is unreachable? The refresh fails gracefully with an error message and the existing cached version is retained.
- What happens when an OpenNeuro dataset has no `participants.tsv`? Only `dataset_description.json` and sidecar JSON fields are extracted; the adapter reports which files were found.
- What happens when a curator corrects a unit but other elements depend on the old hash? A transform is created linking old→new hash; schemas referencing the old hash are flagged for review.
- What happens when re-enrichment produces a lower-confidence annotation than an existing curated one? The curated annotation is preserved; the automated one is offered as a secondary annotation for review.
- What happens when two ontologies define the same concept (e.g., "Echo Time" in both DICOM and RadLex)? Both annotations are stored with their respective ontology labels; the primary annotation is the one with the highest score.
- What happens when the discovery service finds a dataset that was already ingested? It checks the dataset version/timestamp and only re-ingests if the metadata has changed.
- What happens when LLM enrichment hallucinates an ontology URI? All LLM-proposed URIs are validated against the ontology store before being presented as proposals; unresolvable URIs are rejected with an explanation.
- What happens when batch LLM enrichment is expensive (many API calls)? The system respects rate limits, tracks token usage, and allows curators to set a budget per batch run.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The ontology store MUST support loading ontologies from OWL, OBO, and TTL formats via URL or local file path.
- **FR-002**: The system MUST integrate HoMBA (brain anatomy), NIDM (neuroimaging data model), DICOM data element dictionary, RadLex (radiology), and ReproSchema library as ontology/vocabulary sources.
- **FR-003**: After adding new ontologies, enrichment coverage on BIDS+NWB+DANDI elements MUST increase from the current ~10% to at least 40%.
- **FR-004**: The system MUST support ingesting schema descriptors from OpenNeuro datasets via datalad — scanning each dataset for all CSV/TSV files (participants.tsv, phenotype/*.tsv, etc.) and their corresponding JSON sidecars that describe columns, extracting elements from column headers with data types inferred from values.
- **FR-004a**: The system MUST ingest schema descriptors from the ReproSchema library (activities and items) and from stats/mapping repositories containing JSON field mappings (e.g., ABCD, HCP data dictionaries).
- **FR-005**: When multiple datasets use the same BIDS field, the existing element MUST gain additional provenance entries (merge), not create duplicate elements.
- **FR-006**: Curators MUST be able to review, approve, or reject enrichment-assigned ontology annotations on any element.
- **FR-007**: When a curator modifies a semantic field (unit, data_type, pattern), a new element version MUST be created with a new sha256, and a curation_update transform MUST link old→new.
- **FR-008**: Curated annotations MUST NOT be overwritten by subsequent automated enrichment runs.
- **FR-009**: The enrichment pipeline MUST support re-enriching a specific element on demand (via chat or admin action) using the latest ontology store.
- **FR-010**: An ontology management interface MUST display loaded ontologies with term counts, refresh status, and enable/disable controls.
- **FR-011**: Source registration MUST support auto-detection of adapter type from repository URLs and preview of extracted entities before committing to the registry.
- **FR-012**: The chat interface MUST support triggering ontology refresh, element re-enrichment, and source ingestion via natural language commands.
- **FR-013**: The system MUST automatically discover new datasets from pre-approved repository endpoints (OpenNeuro API, DANDI API) on a configurable schedule.
- **FR-014**: Datasets from pre-approved sources with known adapters MUST be auto-ingested without curator approval; datasets from unknown sources MUST be queued for curator review.
- **FR-015**: An ingestion queue interface MUST show pending, in-progress, completed, and failed ingestions with metadata, adapter, and entity counts.
- **FR-016**: The system MUST provide LLM-powered enrichment skills: ontology mapping with reasoning, unit inference with justification, cross-source element alignment assessment, and description generation.
- **FR-017**: LLM enrichment proposals MUST be presented as reviewable diffs — not auto-applied — unless the curator explicitly enables auto-apply for high-confidence results.
- **FR-018**: Batch LLM enrichment MUST be supported — a curator can request enrichment of all unannotated elements from a specific source, with progress tracking.

### Key Entities

- **OntologySource**: A registered ontology with name, URL, format (OWL/OBO/TTL), term count, last refresh timestamp, active status, and embedding index path.
- **ElementVersion**: A link between two elements where one supersedes the other — old_sha256, new_sha256, change_type (curation_update, semantic_correction), curator, timestamp.
- **DataRepository**: A registered data source URL with adapter type, last ingestion timestamp, entity counts, and approval status (pre-approved / pending / rejected).
- **IngestionJob**: A queued or completed ingestion run — repository reference, adapter used, status (pending/running/completed/failed), entity counts, curator who approved (if applicable), timestamps.
- **LLMEnrichmentProposal**: A proposed change from LLM enrichment — element reference, proposed annotation/unit/description, reasoning text, confidence, status (pending/approved/rejected).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The ontology store includes at least 4 new domain-specific ontologies (HoMBA, NIDM, DICOM, RadLex) with a combined term count exceeding 50,000.
- **SC-002**: Enrichment coverage on BIDS+NWB+DANDI elements reaches at least 40% (up from ~10%).
- **SC-003**: At least 10 OpenNeuro datasets can be ingested, producing new elements with proper provenance.
- **SC-004**: Curators can approve/reject individual ontology annotations and the decision persists across re-enrichment.
- **SC-005**: Semantic field changes on curated elements produce new element versions with linked transforms.
- **SC-006**: The ontology admin interface shows term counts and refresh status for all loaded ontologies.
- **SC-007**: New datasets from OpenNeuro are auto-discovered and ingested within 24 hours of publication, without curator intervention.
- **SC-008**: LLM-powered enrichment produces ontology annotations with reasoning text for at least 80% of unannotated elements when run in batch mode.

## Clarifications

### Session 2026-03-30

- Q: Should source discovery be manual (curator-provided URLs) or automated? → A: Automated discovery from pre-approved repository endpoints (OpenNeuro, DANDI) with auto-ingestion via known adapters; unknown sources queued for curator approval. Pre-built adapters for approved resources run without human intervention.
- Q: Should the service integrate LLM operations for knowledge improvement? → A: Yes — LLM skills for ontology mapping with reasoning, unit inference, cross-source alignment, and description generation. Proposals presented as reviewable diffs, batch mode supported.
- Q: What additional vocabulary sources? → A: ReproSchema library (activities/items as data element definitions) and stats/mapping repos with JSON field mappings (ABCD, HCP data dictionaries).
- Q: How to access OpenNeuro datasets? → A: Via datalad, scanning each dataset for all CSV/TSV files and corresponding JSON sidecars that describe columns, not just participants.tsv.

## Scope Boundaries

### In Scope

- HoMBA, NIDM, DICOM, RadLex ontology integration
- OpenNeuro dataset ingestion adapter
- Generic repository ingestion via existing adapter framework
- Annotation review/approve/reject workflow
- Element versioning with curation_update transforms
- Ontology store management interface
- Source discovery and registration via chat
- Re-enrichment of specific elements on demand

### Out of Scope

- Custom ontology creation (curators use existing ontologies, not build new ones)
- Cross-ontology term alignment (e.g., mapping DICOM to RadLex equivalents)
- Ontology editing (the system consumes ontologies, not produces them)

## Assumptions

- HoMBA is available as OWL/OBO from the GitHub repository
- NIDM terms are available from the NIDM-Terms repository (https://github.com/incf-nidash/nidm-terms)
- DICOM data element dictionary is available as a structured format (CSV or XML from DICOM standard)
- RadLex is available as OWL from the RSNA RadLex site
- OpenNeuro datasets are accessible via the OpenNeuro API or direct S3 access
- The existing embedding model (all-MiniLM-L6-v2) works for domain-specific terms
- Element versioning uses the existing transform model with a new function_type "curation_update"

## Dependencies

- Feature 029 (Backend service) — provides GraphQL API and pipeline infrastructure
- Feature 033 (Unit Standardization) — provides QUDT unit resolution
- Feature 034 (Curation Interface) — provides chat-based curation workflow
- Feature 035 (UX Overhaul) — provides entity cross-links and dense UI
