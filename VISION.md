# undata: A Universal Data Element Registry

## The Problem

Neuroscience has no shared language for data elements.

Five major ecosystems — BIDS, NWB, DANDI, openMINDS, and AIND — each define
their own schemas for the same underlying concepts. A field called `age` in BIDS
means the same thing as `Age` in openMINDS and `age` in AIND, but there is no
machine-readable way to know this. The schemas live in different formats (JSON
Schema, YAML, LinkML, Python classes, JSON-LD), use different conventions, and
evolve independently.

This creates three concrete problems:

### 1. Schema Fragmentation

A researcher working across ecosystems must manually learn each schema language.
Tools built for one ecosystem cannot interoperate with another. There is no way
to ask "what does BIDS call the thing that NWB calls `ElectricalSeries`?" and
get a precise, machine-readable answer.

### 2. Identity Conflation

Existing systems conflate *what something is* with *where it came from*. An
`age` field defined in BIDS and an `age` field defined in AIND are treated as
different things because they have different sources — even when they represent
the identical concept with the same data type, unit, and constraints. Conversely,
two fields with the same name but different semantics (string vs. integer, years
vs. days) may be incorrectly assumed to be the same.

### 3. Invisible Transformations

When data moves between ecosystems, the transformations applied are undocumented.
A unit conversion from days to years, a type coercion from string to integer, a
value mapping from coded integers to human-readable labels — these happen silently
in scripts, with no provenance record. Reproducibility suffers because the
transformation chain is invisible.

## The Solution

undata is a **content-addressed registry of data elements** that extracts schema
definitions from heterogeneous sources, assigns each element a stable identity
based on what it *means* rather than where it *came from*, and makes the
relationships and transformations between elements explicit and machine-readable.

### Three Innovations

**Content-addressed identity.** Each data element gets a SHA-256 hash computed
from its semantic properties — data type, unit, pattern, constraints, and (when
available) its ontology grounding. Two elements from different sources that
describe the same concept produce the same hash and are recognized as the same
entity. The hash changes only when the meaning changes.

**Identity ≠ provenance.** An element's identity (what it is) is separated from
its provenance (where it came from). A single element can accumulate provenance
from multiple sources. When BIDS and openMINDS both define an `age` field with
the same type and unit, the registry contains one element with two provenance
entries — not two elements that must be manually reconciled.

**Explicit transformations.** When two elements share an ontology concept but
differ in type, unit, or encoding, the registry generates an explicit transform
record documenting how to convert between them. These transforms have their own
content-addressed identities and provenance chains.

## What undata Produces

From a collection of source schemas, undata produces:

- **Elements**: Field-level data definitions (e.g., `age`, `weight`, `diagnosis`)
  with data type, unit, constraints, and ontology annotations
- **Schemas**: Class-level definitions (e.g., `Subject`, `Session`, `Electrode`)
  with property lists, inheritance, and mixins
- **Values**: Individual categorical concepts (e.g., `male`, `right-handed`,
  `MRI`) with ontology grounding
- **Value Sets**: Named collections of values (e.g., `handedness_options`,
  `modality_types`)
- **Transforms**: Documented conversions between elements (unit conversion,
  type coercion, value mapping)
- **Curation Flags**: Quality review items for low-confidence matches,
  ambiguous annotations, and unrecognized patterns
- **Alignment Reports**: Cross-source alias groups showing which elements from
  different sources refer to the same concept

## How It Works

The system operates as a six-stage pipeline:

```
Source Schemas ──→ Extract ──→ Enrich ──→ Align ──→ Commit ──→ Transform
  (BIDS, NWB,      (adapters    (ontology    (cross-source  (content     (conversion
   DANDI, etc.)      → LinkML     matching,    alias          addressing,  pattern
                     → entities)   LLM verify)  detection,     dedup,       detection)
                                               annotation     merge)
                                               transfer)
```

1. **Extract**: Source-specific adapters convert each schema into a common
   intermediate representation (LinkML SchemaDefinition), then a standard
   extractor produces classified entities with semantic identity and provenance.
   Entities are written to a staging area with temporary UUIDs.

2. **Enrich**: Each staged entity is matched against the knowledge service —
   a continuously expanding collection of ontologies, data repositories,
   knowledge bases, and schema registries. Embedding similarity finds
   candidates, LLM verification evaluates borderline matches, and ontology
   hierarchy traversal assigns annotations at multiple SKOS precision levels
   (exactMatch, closeMatch, broadMatch, narrowMatch, relatedMatch). Source
   metadata with curated ontology IDs is assigned directly (highest confidence).
   Enrichment modifies staged entities in-place — no new files are created.

3. **Commit**: Enriched entities are content-addressed. The identity hash is
   computed from the semantic block (including ontology annotations if
   high-confidence). The hash determines whether an entity is new or already
   exists in the registry. Cross-source duplicates are merged (provenance
   accumulated, single identity preserved). Staging is cleared after commit.

4. **Align**: Runs after all sources have been extracted and enriched.
   Alignment detects cross-source aliases — entities from different sources
   that refer to the same concept. It uses embedding similarity and shared
   ontology terms to identify groups of equivalent entities. Cross-source
   annotation transfer propagates ontology annotations from well-annotated
   entities (e.g., openMINDS at 70%) to under-annotated ones (e.g., NWB at
   1%). Alignment results can inform the commit hash — if two entities are
   aligned, their ontology annotations converge, producing the same
   content-addressed identity.

5. **Commit**: Aligned, enriched entities are content-addressed. The identity
   hash is computed from the semantic block (including ontology annotations).
   The hash determines whether an entity is new or already exists in the
   registry. Cross-source duplicates are merged (provenance accumulated, single
   identity preserved).

6. **Transform**: For aligned elements with differing types, units, or
   encodings, explicit transform records are generated with documented
   conversion logic.

Each stage reads from and writes to a **storage backend** — either flat YAML
files on disk (for standalone CLI use) or a database (for the web service).

## Who Uses It

- **Data engineers** building cross-ecosystem pipelines use the registry to find
  equivalent fields and generate conversion code.
- **Standards developers** use it to compare their schema with others and
  identify gaps or redundancies.
- **Curators** review low-confidence matches and ambiguous annotations through
  a web interface, improving registry quality over time.
- **Contributors** suggest annotations, flag issues, and comment on entities
  through an authenticated submission workflow.
- **Tool builders** query the GraphQL API to power search, autocomplete, and
  validation in their applications.
- **Researchers** browse the registry to understand what data elements exist
  across ecosystems and how they relate.

## Community Model (Inspired by CivicDB)

The curation and contribution system is modeled after
[CivicDB](https://civicdb.org) — a production biomedical knowledgebase with a
proven social curation workflow.

### Roles and Engagement

**Three-tier roles.** Contributor (default — can submit annotations, comments,
and flags) → Curator (reviews and resolves submissions) → Admin (manages users,
triggers pipelines). Every action is attributed to an authenticated identity.

**Graduated engagement.** Anonymous browse (no login) → comment/discuss → flag
issues → suggest annotations → submit evidence → editorial review. Each step
has lower friction than the next, creating a natural onboarding funnel. Curator
promotion requires demonstrated activity (minimum submissions, accepted
contributions).

### Curation Workflow

**Revision-based curation.** Contributions are not applied directly. A
contributor submits a suggestion (e.g., "this element should be annotated with
NCIT:C25150"). A curator reviews the suggestion with supporting evidence
(embedding score, LLM justification, related entities) and approves, rejects, or
defers. Field-level diffs show exactly what changes.

**Evidence panels.** When reviewing a curation flag, the curator sees:
- The automated match candidates with similarity scores
- LLM verification results (model, justification, confidence)
- Related entities from other sources with the same ontology term
- The entity's full provenance chain

**Polymorphic concerns.** Any entity type (element, schema, value, valueset,
transform) can be commented on, flagged, and subscribed to. This avoids
entity-type-specific UI for generic operations.

### UI Design Patterns

The web interface serves three audiences simultaneously — browsers seeking
information, contributors participating in curation, and curators reviewing
submissions. Following CivicDB's approach:

**Entity browse pages.** Filterable data grids for each entity type with
entity-specific columns. Every count is a clickable link (e.g., "5 transforms"
navigates to those transforms). Multi-column sort, per-column filters, cursor
pagination.

**Entity detail pages.** Consistent layout across entity types: identity block
(hash, type, unit) → semantic content → provenance chain → ontology annotations
→ related entities (transforms, schemas, alias group members). Inline curation
status indicators (pending/approved/rejected) make review state visible while
browsing.

**Connected entity navigation.** Entities link bidirectionally: an element page
lists its transforms; a transform page links back to source and target elements;
a schema page lists its properties (elements). Users traverse the knowledge
graph in any direction.

**Curation queue.** Pending flags grouped by type (low_confidence,
ambiguous_match, etc.) with evidence panels. Curators claim items, review
evidence, and resolve with a note. Pre-populated forms reduce friction between
"this needs review" and "I'm reviewing this."

**Activity feed.** Platform-wide timeline of curation events: flag created,
contribution submitted, flag resolved, entity re-enriched. Filterable by action
type, user, source. Each entity has its own revision history.

**Community features.** User profiles with contribution statistics and activity
history. Organization-level attribution. Leaderboards for curation activity.
Notification system for subscribed entities and @mentions.

**Source suggestion queue.** Users suggest new sources or ontologies by
submitting a reference with a relevance comment. Curators triage and approve.
Approved sources enter the pipeline automatically.

### API Design

**GraphQL-only API.** Following CivicDB's architecture, the same GraphQL API
powers both the frontend and external consumers. No separate REST layer. Relay-
style cursor pagination, DataLoader batching, and materialized views for
performance.

**Activity trail.** All state changes (flag created, contribution submitted,
flag resolved, entity re-enriched) produce audit records. The full history of
any entity is browsable through the API.

---

# Blueprint: Iteration 2

The following blueprint incorporates lessons from the 27-feature exploration
phase ("brainstorm v1") and defines the architecture for a production system.

## Guiding Principles

1. **Library is the engine.** All pipeline logic lives in the Python library.
   The backend is a thin service layer that calls library functions and stores
   results in a database. The CLI and the API produce identical output.

2. **Storage is pluggable.** Pipeline functions accept a storage backend
   interface. The file backend writes YAML to disk. The database backend writes
   to PostgreSQL. The library never imports SQLAlchemy directly — the database
   backend is provided by the backend package.

3. **LinkML is the intermediate representation.** Every source adapter produces
   a LinkML SchemaDefinition. A single standard extractor converts
   SchemaDefinition to classified entities. No adapter does its own entity
   classification.

4. **Content addressing is the identity model.** Entity identity is determined
   by semantic content, not by source or filename. Two-mode hashing
   (ontology-anchored for grounded entities, structural fallback for
   ungrounded) is the foundation.

5. **Enrichment is iterative and improvable.** The ontology store, embedding
   model, and LLM verifier are all replaceable. Enrichment quality improves
   over time through better models, expanded ontologies, and curator feedback.
   The system is designed to re-enrich the entire registry when models improve.

6. **Curation is first-class.** Every automated decision that falls below a
   confidence threshold produces a curation flag. Curators resolve flags
   through the UI. Resolved flags feed back into the system as ground truth.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        Frontend                             │
│   Next.js · Apollo Client · Playwright tests                │
│   Entity browser · Curation queue · Community · Dashboard   │
└──────────────────────────┬──────────────────────────────────┘
                           │ GraphQL
┌──────────────────────────┴──────────────────────────────────┐
│                        Backend                              │
│   FastAPI · Strawberry GraphQL · Auth (OIDC + API keys)     │
│   Task manager (async jobs) · Thin service layer            │
├─────────────────────────────────────────────────────────────┤
│                   Storage Layer                              │
│   PostgreSQL 16 (JSONB entities, provenance, audit log)     │
│   pgvector (embeddings, similarity search)                  │
│   RDF store (ontology terms, hierarchy, SPARQL)             │
│   Search index (full-text entity search)                    │
│   All behind StorageBackend protocol                        │
└──────────────────────────┬──────────────────────────────────┘
                           │ StorageBackend protocol
┌──────────────────────────┴──────────────────────────────────┐
│                        Library                              │
│   Pipeline: extract → enrich → align → commit → transform   │
│   Adapters: BIDS, NWB, DANDI, openMINDS, AIND, ...         │
│   Ontology store · Embeddings · LLM verification            │
│   Hashing · Curation flags · Run summaries                  │
├─────────────────────────────────────────────────────────────┤
│                   Storage Layer (File)                       │
│   YAML flat files · Parquet vectors · pyoxigraph RDF        │
│   Implements StorageBackend protocol                        │
└─────────────────────────────────────────────────────────────┘
```

### Package Boundaries

```
undata-library              (core, no DB deps)
  ├── models                entity definitions, enums, protocols
  ├── pipeline              extract, enrich, commit, align, transform
  ├── adapters              source-specific → LinkML → entities
  ├── ontology              RDF store, search, vector index
  ├── enrichment            similarity, LLM verification, annotation
  ├── hashing               content addressing, URI generation
  ├── curation              flags, run summaries, discovery
  ├── storage               StorageBackend protocol + FileBackend
  └── cli                   command-line interface

undata-backend              (depends on undata-library)
  ├── db                    SQLAlchemy models, session, DatabaseBackend
  ├── graphql               Strawberry types, queries, mutations
  ├── auth                  OIDC middleware, API keys, RBAC
  └── main                  FastAPI app, lifespan, CORS

undata-frontend             (standalone, talks to backend via GraphQL)
  ├── app/                  Next.js pages
  ├── components/           Reusable UI
  ├── graphql/              Queries, mutations, types
  └── tests/                Playwright E2E
```

### StorageBackend Protocol

The central abstraction that enables library reuse:

```
StorageBackend
  read(entity_type, identifier) → entity dict | None
  write(entity_type, entity dict) → identifier
  list(entity_type, filters?) → iterator of entity dicts
  exists(entity_type, identifier) → bool
  delete(entity_type, identifier) → bool
  merge_provenance(entity_type, identifier, new_provenance) → entity dict
  count(entity_type, filters?) → int

FileBackend(base_dir: Path)              ← current YAML behavior
DatabaseBackend(session: AsyncSession)   ← PostgreSQL via SQLAlchemy
```

Pipeline functions accept `backend: StorageBackend` instead of `Path`:

```python
# Works with either backend
def commit_staged(staging: StorageBackend, output: StorageBackend) → stats
def enrich_elements(backend: StorageBackend, onto_store, ...) → stats
def align_elements(backend: StorageBackend, ...) → stats
```

### Polyglot Storage

Different data types have fundamentally different access patterns. A single
relational database is not the right store for everything. The storage layer
uses the right tool for each kind of data:

| Data | Access Pattern | File Backend | DB Backend |
|------|---------------|--------------|------------|
| Entities (elements, schemas, values, valuesets) | CRUD, filter, paginate | YAML files | PostgreSQL JSONB |
| Provenance chains | Append, query by source | Nested in YAML | JSONB arrays or normalized tables |
| Ontology terms + hierarchy | Graph traversal, SPARQL, label search | pyoxigraph (local RDF) | RDF store or PostgreSQL with ltree/recursive CTE |
| Embeddings (entity + ontology) | Nearest-neighbor, cosine similarity | Parquet + numpy | pgvector |
| Full-text search | Keyword search, faceted filtering | grep / in-memory | Search index (Meilisearch or PostgreSQL tsvector) |
| LLM verification cache | Key-value lookup by (model, element, term) | JSON file | PostgreSQL table |
| Curation flags + contributions | CRUD, status filter, queue ordering | YAML files | PostgreSQL |
| Run summaries + audit log | Append-only, time-range queries | YAML files | PostgreSQL |
| Source definitions | Read-only config | Bundled YAML | PostgreSQL or config files |

The StorageBackend protocol abstracts over these — a `FileBackend` composes
YAML files + parquet + pyoxigraph, while a `DatabaseBackend` composes
PostgreSQL + pgvector + RDF store + search index. Pipeline functions don't know
which backend they're using.

The library ships with no database dependencies. The `DatabaseBackend`
implementation lives in the backend package and depends on SQLAlchemy, asyncpg,
etc. Installing `undata-library` alone gives you the `FileBackend` only.

### Task Manager

Pipeline operations can take minutes to hours — full re-extraction across 5
sources, ontology refresh (downloading and loading 13 ontologies), LLM batch
verification of thousands of entity pairs, or re-enrichment after a model
upgrade. These cannot be synchronous request-response.

The backend needs an async task manager:

- **Task lifecycle**: submitted → queued → running → completed/failed
- **Progress reporting**: tasks report progress (e.g., "enriching: 1,234 / 8,820
  entities") visible through the API and UI
- **Cancellation**: long-running tasks can be cancelled by the user
- **Retry**: failed tasks can be retried with the same or modified parameters
- **Concurrency control**: some tasks are mutually exclusive (e.g., two pipeline
  runs for the same source should not overlap)
- **Result access**: completed tasks produce results (run summaries, entity
  counts) accessible through the API

Candidate implementations: Celery + Redis, arq, or Dramatiq for the backend;
the library itself remains synchronous (the task manager wraps library calls in
async workers). The GraphQL API exposes task status through queries and
mutations:

```
triggerPipelineRun(source) → Task       # returns immediately with task ID
taskStatus(id) → Task                   # poll for progress
cancelTask(id) → Task                   # request cancellation
tasks(status?, first?, after?) → TaskConnection  # browse task history
```

### Entity Model

Four entity types, all following the same structure:

```
Entity
  ├── sha256: str                     content hash (identity)
  ├── semantic: dict                  type-specific semantic block
  │     ├── (Element) data_type, unit, pattern, constraints, type_ref
  │     ├── (Schema)  properties[], subclass_of, mixins[], is_mixin
  │     ├── (Value)   label, description
  │     └── (ValueSet) name, members[]
  ├── provenance: [ProvenanceEntry]   where it came from (accumulates)
  │     └── source, class, name, description, PROV-O fields
  ├── ontology_annotations: [OntologyAnnotation]  what it means
  │     └── term_uri, term_label, ontology, relation, match_level,
  │         score, model, primary
  └── curation_flags: [CurationFlag]  quality review items
```

Plus supporting entities:
- **Transform**: source_element → target_element with function spec
- **CurationFlag**: entity_ref + flag_type + status + evidence
- **RunSummary**: pipeline execution record with counts and timing
- **UserProfile**: authenticated user with role
- **Contribution**: user-submitted annotation, comment, or edit

### Adapter Architecture

Every adapter follows the same pattern:

```
Source Schema (any format)
  ↓ adapter.to_linkml()
LinkML SchemaDefinition (in-memory)
  ↓ LinkMLExtractor.extract()
[ClassifiedEntity, ...]
```

The adapter's job is *only* to build a LinkML SchemaDefinition. Classification,
provenance stamping, deduplication, and routing all happen in the standard
extractor. This eliminates the 51 cross-adapter misclassification issues found
in brainstorm v1.

Each adapter is a Python class:

```python
class BIDSAdapter(BaseAdapter):
    name = "bids"

    def to_linkml(self, source_path: Path, **opts) -> SchemaDefinition:
        """Build LinkML schema from BIDS specification."""
        ...
```

### GraphQL API

Based on the validated contract from feature 027:

**Queries** (public, no auth required):
- Single lookups: `element(sha256)`, `schema(sha256)`, `value(sha256)`, `valueset(sha256)`
- Browse with filters + cursor pagination: `browseElements`, `browseSchemas`, `browseValues`, `browseTransforms`
- Curation: `curationQueue(status, flagType)`, `contributions(status)`
- Pipeline: `runSummaries(source)`, `latestRun(source)`

**Mutations** (authenticated):
- Curation: `resolveFlag`, `batchResolveFlags`
- Contributions: `submitContribution`, `reviewContribution`
- Pipeline: `triggerPipelineRun`, `importRegistry`

**Pagination**: Relay-style cursor pagination on all browse queries.

### Authentication

- OIDC via Keycloak (GitHub, ORCID as external providers)
- JWT validation middleware on all mutations
- API key support for scripts and CI
- Four roles: viewer (default), contributor, curator, admin
- Queries are always public

### Knowledge Service

A key lesson from brainstorm v1: enrichment was limited by the knowledge
available to it. The ontology store had 268K terms from 13 ontologies, but
domain-specific concepts (MRI sequences, EEG montages, specific assay types)
were absent. The system declared "ontology not rich enough" and stopped — instead
of actively seeking richer sources. Ontology annotation was effectively exact
match only, despite the SKOS multi-precision model being designed in.

Iteration 2 introduces a **knowledge service** — a continuously expanding
collection of neuroscience knowledge resources that the enrichment pipeline draws
from. This is not just ontologies; it's any structured source that can inform
entity annotation:

**Ontologies** (formal term hierarchies):
- Core biomedical: NCIT, PATO, UBERON, HP, OBI, CHEBI, EFO, MONDO
- Neuroscience-specific: NEMO (neural electrophysiology), CogPO (cognitive
  paradigms), NIF-std (neuroscience information framework), ReproNim terms
- Imaging: DICOM terminology, RadLex, NeuroNames

**Data repositories** (curated metadata with ontology bindings):
- OpenNeuro (BIDS datasets with rich metadata)
- DANDI (dandisets with NWB + schema.org annotations)
- openMINDS instances (4,390 controlled vocabulary entries with
  preferredOntologyIdentifier)
- NeuroVault (statistical maps with cognitive concept annotations)

**Knowledge bases** (structured concept mappings):
- Cognitive Atlas (cognitive concepts → tasks → contrasts → disorders)
- InterLex (NIF term registry, cross-references to major ontologies)
- NITRC (neuroimaging tools and resources with tagged capabilities)
- NeuroSynth / NeuroQuery (term → brain region associations)

**Schema registries** (data element definitions from other domains):
- NIH CDE Repository (Common Data Elements)
- CDISC (clinical trial data standards)
- FHIR resources (health data interoperability)
- schema.org (general-purpose structured data vocabulary)

The knowledge service:

1. **Ingests resources** using the same adapter pattern as data sources.
   Each knowledge resource gets an adapter that produces structured terms,
   mappings, or annotations in a common format.

2. **Indexes for enrichment** — terms are embedded, indexed for full-text
   search, and loaded into the RDF store with hierarchy and cross-references.

3. **Enables multi-precision annotation.** With richer knowledge, the system
   can assign annotations at all SKOS levels:
   - **exactMatch**: Entity maps directly to an ontology term
     (e.g., `age` → NCIT:C25150 "Age")
   - **closeMatch**: Entity is very similar but not identical
     (e.g., `age_at_scan` → NCIT:C25150 with qualifier)
   - **broadMatch**: Entity is a specialization of a broader term
     (e.g., `t1w_acquisition_time` → DICOM:AcquisitionTime)
   - **narrowMatch**: Entity is more general than a specific term
   - **relatedMatch**: Entity is conceptually related
     (e.g., `diagnosis` → MONDO:disease via Cognitive Atlas task→disorder)

4. **Discovers gaps.** When enrichment cannot find a match for an entity, the
   knowledge service records the miss. Accumulated misses by domain (e.g., "247
   MRI-related entities have no ontology match") surface as actionable gaps that
   guide which resources to ingest next.

5. **Grows through curation.** Curator-approved annotations become ground truth
   that improves future enrichment. When a curator maps an entity to a term not
   in the knowledge store, the service can ingest that term's ontology to cover
   related concepts.

**Embedding and similarity:**
- sentence-transformers (all-MiniLM-L6-v2 or domain-tuned model)
- Stored in pgvector (DB) or parquet (file)
- Used for candidate retrieval, alias detection, and gap analysis

**LLM verification:**
- Batch verification of borderline matches (0.4–0.7 similarity range)
- litellm (OpenAI) or ollama (local), with disk/DB cache
- LLM receives term label + definition + synonyms for informed evaluation

**Source metadata pre-enrichment:**
- Directly assign ontology IDs from source data (e.g., openMINDS
  preferredOntologyIdentifier) before embedding search — this is the highest
  confidence path and produced 70% enrichment for openMINDS in brainstorm v1

### What Changed from Brainstorm v1

| Aspect | Brainstorm v1 | Iteration 2 |
|--------|---------------|-------------|
| Adapters | Each does own classification | All produce LinkML, standard extractor classifies |
| Storage | File-only, import service copies to DB | StorageBackend protocol, polyglot backends |
| Backend | REST routes → wiped → GraphQL (broken) | GraphQL from day 1, thin layer over library |
| Pipeline | Library-only, backend can't call it | Library functions accept backend parameter |
| Pipeline order | Extract → enrich → commit → align | Extract → enrich → align → commit (alignment informs hash) |
| Long tasks | Synchronous only, CLI blocks | Task manager with progress, cancellation, retry |
| Embeddings | Parquet files only | pgvector (DB) or parquet (file) |
| Ontology | pyoxigraph only | RDF store (file) or graph DB/PostgreSQL (backend) |
| Search | None | Full-text search index (Meilisearch or tsvector) |
| LLM cache | JSON file | DB table (backend) or JSON file (CLI) |
| Testing | 343 library tests, no backend/e2e | Library + backend + Playwright from the start |
| Auth | Keycloak config exists, not enforced | OIDC + RBAC enforced on mutations |
| Enrichment | Exact match only, "ontology not rich enough" | Multi-precision SKOS, knowledge service for richer sources |
| UI | Stub pages, no community features | CivicDB-inspired: browse + curate + community integrated |

### Implementation Sequence

**Phase 1: Library core with storage abstraction**
- Define StorageBackend protocol
- Implement FileBackend (wrap current YAML behavior)
- Refactor pipeline functions to accept backend parameter
- Verify all 343 tests pass (zero regressions)
- Refactor adapters to LinkML-first pattern

**Phase 2: Backend service**
- PostgreSQL models matching entity model
- DatabaseBackend implementing StorageBackend protocol
- Strawberry GraphQL with all queries and mutations
- Import service (registry YAML → DB via DatabaseBackend)
- Backend tests against real DB

**Phase 3: Frontend integration**
- Apollo Client wired to all GraphQL queries
- Element browser, schema browser, value browser
- Curation queue with flag resolution
- Run summary dashboard
- Playwright E2E tests

**Phase 4: Authentication & polish**
- OIDC middleware with Keycloak
- Role-based mutation access
- API key support
- CI pipeline (library → backend → frontend → e2e)

**Phase 5: Knowledge service & enrichment**
- Knowledge service ingesting neuroscience ontologies, data repositories,
  knowledge bases, and schema registries
- Multi-precision SKOS annotation (exact, close, broad, narrow, related)
- Gap analysis: track unmatched entities by domain, surface actionable gaps
- Ground truth from curator decisions feeds back into enrichment
- Domain-tuned embedding model trained on neuroscience terminology
- Cross-source annotation transfer in alignment stage

## Validated Knowledge from Brainstorm v1

These findings are confirmed through implementation and testing:

**Entity counts from 5 sources** (latest extraction):
- 2,191 elements, 915 schemas, 5,500 values, 214 valuesets
- 5,166 entities enriched (59%), 15,699 curation flags

**Enrichment rates by source**:
- BIDS: 10.3% (gap: MRI/EEG/PET terms not in ontology store)
- openMINDS: 70% (source metadata provides curated ontology IDs)
- DANDI: 25.9%, AIND: 34.4%, NWB: 1.1%

**LLM verification performance**:
- gpt-5.4-nano: 0.06s/pair in batches of 30
- ollama/qwen3.5: 0.5s/pair in batches of 30
- 5/5 accuracy on sampled matches
- Requires `think: false` for qwen3.5 to avoid empty responses

**Content addressing**:
- Two-mode hashing works correctly — ontology-anchored entities merge
  cross-source, structural fallback prevents false merges
- Short key (12 hex chars / 2^48 space) sufficient for current scale

**Ontology store**:
- 13 ontologies, 2.99M terms total, 268K embedded
- pyoxigraph handles the scale without issues
- Gap: domain-specific terms (MRI sequences, EEG montages, cognitive paradigms)
  not covered — enrichment effectively did exact match only and gave up when
  ontology terms were absent. This motivates the knowledge service in iteration 2

**Adapters** (all 5 validated with LinkML-first pattern):
- BIDS: 214 schemas, 585 elements, 494 values (sidecar rules → mixins)
- NWB: 80 classes with inheritance, 46 attributes with type_ref
- openMINDS: 202 classes, 473 attributes, 4,390 instance values
- DANDI: Pydantic models → classes, proper Union/enum handling
- AIND: JSON Schema $defs → classes/enums, $ref → slot ranges

**Frontend patterns worth keeping**:
- Apollo Client cursor pagination with merge policies
- shadcn/ui + Tailwind CSS component library
- Dual-path URL resolution (Docker internal vs browser external)

**Backend patterns worth keeping**:
- Async SQLAlchemy 2.x with asyncpg
- Strawberry GraphQL with FastAPI native integration
- JSONB denormalization for semantic/provenance (filter without joins)
- Thread pool delegation for blocking library operations
- Structured JSON logging
