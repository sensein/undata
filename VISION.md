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
Source Schemas ──→ Extract ──→ Enrich ──→ Commit ──→ Align ──→ Transform
  (BIDS, NWB,      (adapters    (ontology    (content     (cross-source  (conversion
   DANDI, etc.)      → LinkML     matching,    addressing,   alias         pattern
                     → entities)   LLM verify)  dedup,        detection)    detection)
                                               merge)
```

1. **Extract**: Source-specific adapters convert each schema into a common
   intermediate representation (LinkML SchemaDefinition), then a standard
   extractor produces classified entities with semantic identity and provenance.
   Entities are written to a staging area with temporary UUIDs.

2. **Enrich**: Each staged entity is matched against an ontology store (268,000+
   terms from 13 ontologies) using embedding similarity, with LLM verification
   for borderline matches. Ontology annotations are assigned at multiple
   precision levels (exactMatch, closeMatch, broadMatch, relatedMatch).
   Enrichment modifies staged entities in-place — no new files are created.

3. **Commit**: Enriched entities are content-addressed. The identity hash is
   computed from the semantic block (including ontology annotations if
   high-confidence). The hash determines whether an entity is new or already
   exists in the registry. Cross-source duplicates are merged (provenance
   accumulated, single identity preserved). Staging is cleared after commit.

4. **Align**: Runs *after* commit, on the full committed registry. This is
   necessary because alignment detects cross-source aliases — it needs entities
   from all sources to be committed and content-addressed before it can compare
   them. Embedding-based similarity and shared ontology terms identify groups of
   equivalent entities. Cross-source annotation transfer propagates ontology
   annotations from well-annotated entities (e.g., openMINDS at 70%) to
   under-annotated ones (e.g., NWB at 1%).

5. **Transform**: For aligned elements with differing types, units, or
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
proven social curation workflow. Key patterns adopted:

**Three-tier roles.** Contributor (default — can submit annotations, comments,
and flags) → Curator (reviews and resolves submissions) → Admin (manages users,
triggers pipelines). Every action is attributed to an authenticated identity.

**Revision-based curation.** Contributions are not applied directly. A
contributor submits a suggestion (e.g., "this element should be annotated with
NCIT:C25150"). A curator reviews the suggestion with supporting evidence
(embedding score, LLM justification, related entities) and approves, rejects, or
defers. Field-level diffs show exactly what changes.

**Polymorphic concerns.** Any entity type (element, schema, value, valueset,
transform) can be commented on, flagged, and subscribed to. This avoids
entity-type-specific UI for generic operations.

**Evidence panels.** When reviewing a curation flag, the curator sees:
- The automated match candidates with similarity scores
- LLM verification results (model, justification, confidence)
- Related entities from other sources with the same ontology term
- The entity's full provenance chain

**Activity trail.** All state changes (flag created, contribution submitted,
flag resolved, entity re-enriched) produce audit records. The full history of
any entity is browsable.

**GraphQL-only API.** Following CivicDB's architecture, the same GraphQL API
powers both the frontend and external consumers. No separate REST layer. Relay-
style cursor pagination, DataLoader batching, and materialized views for
performance.

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
│   Element browser · Curation queue · Run dashboard          │
└──────────────────────────┬──────────────────────────────────┘
                           │ GraphQL
┌──────────────────────────┴──────────────────────────────────┐
│                        Backend                              │
│   FastAPI · Strawberry GraphQL · Auth (OIDC + API keys)     │
│   Thin service layer: calls library, stores in DB           │
├─────────────────────────────────────────────────────────────┤
│                   Storage Backend (DB)                       │
│   PostgreSQL 16 · pgvector · JSONB entities                 │
│   Implements StorageBackend protocol                        │
└──────────────────────────┬──────────────────────────────────┘
                           │ StorageBackend protocol
┌──────────────────────────┴──────────────────────────────────┐
│                        Library                              │
│   Pipeline: extract → enrich → commit → align → transform   │
│   Adapters: BIDS, NWB, DANDI, openMINDS, AIND, ...         │
│   Ontology store · Embeddings · LLM verification            │
│   Hashing · Curation flags · Run summaries                  │
├─────────────────────────────────────────────────────────────┤
│                   Storage Backend (File)                     │
│   YAML flat files on disk                                   │
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

### Ontology & Enrichment

- **Ontology store**: pyoxigraph RDF with 13 ontologies (268K+ terms)
- **Embeddings**: sentence-transformers (all-MiniLM-L6-v2 or domain-tuned)
  stored in pgvector (DB) or parquet (file)
- **LLM verification**: Batch verification of borderline matches via
  litellm (OpenAI) or ollama (local). Disk-cached by (model, element, term).
- **Multi-precision**: Annotations at exactMatch, closeMatch, broadMatch,
  relatedMatch using ontology hierarchy traversal
- **Source metadata pre-enrichment**: Directly assign ontology IDs from source
  data (e.g., openMINDS preferredOntologyIdentifier) before embedding search

### What Changed from Brainstorm v1

| Aspect | Brainstorm v1 | Iteration 2 |
|--------|---------------|-------------|
| Adapters | Each does own classification | All produce LinkML, standard extractor classifies |
| Storage | File-only, import service copies to DB | StorageBackend protocol, same pipeline on both |
| Backend | REST routes → wiped → GraphQL (broken) | GraphQL from day 1, thin layer over library |
| Pipeline | Library-only, backend can't call it | Library functions accept backend parameter |
| Embeddings | Parquet files only | pgvector (DB) or parquet (file) |
| LLM cache | JSON file | DB table (backend) or JSON file (CLI) |
| Testing | 343 library tests, no backend/e2e | Library + backend + Playwright from the start |
| Auth | Keycloak config exists, not enforced | OIDC + RBAC enforced on mutations |

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

**Phase 5: Enrichment improvements**
- Ground truth validation dataset from curator decisions
- Fine-tuned embedding model
- Expanded ontology coverage
- Cross-source annotation transfer
- LLM-guided ontology search for uncovered domains

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
- Gap: domain-specific terms (MRI sequences, EEG montages) not covered

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
