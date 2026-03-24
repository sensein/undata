# Research: 027 Library Hardening, Pipeline Optimization, UI/DB Rebuild

## R1: CivicDB Architecture Study

**Decision**: Model the undata UI/DB after CivicDB's architecture — GraphQL API, social curation workflows, connected entity navigation.

**Findings from CivicDB (civicdb.org / griffithlab/civic-v2)**:

- **Tech stack**: Angular frontend + Ruby on Rails 8.0 backend + PostgreSQL (130+ tables, 10 materialized views) + GraphQL-only API (graphql-ruby) + Searchkick/Elasticsearch + Sidekiq + Redis + OmniAuth (GitHub/Google/ORCID)
- **API**: GraphQL-only (no REST). 50 mutations, Relay-style cursor pagination. Same API powers frontend and is publicly available via GraphiQL.
- **Data model**: Feature (Gene/Factor/Fusion/Region) → Variant → MolecularProfile → EvidenceItem/Assertion. Plus Disease, Therapy, Source, ClinicalTrial. Polymorphic delegated_type for Feature subtypes.
- **Social model**: Three-tier — Curator (default, can submit/comment/flag) → Editor (reviews/accepts/rejects, needs email) → Admin. Revision-based workflow with field-level diffs.
- **Curation workflow**: Submit → Suggest Revision (field-level diff) → Editor Review (accept/reject) → Moderate → Approve. Full activity/audit trail.
- **Commenting**: Polymorphic `Commentable` concern on all entities. Markdown support. Entity/user/role mentions.
- **Flagging**: Polymorphic `Flaggable` on all entities. Open → resolved states. Flags are themselves commentable and subscribable.
- **Notifications**: Subscribable concern, in-app + email notifications.
- **Performance**: Materialized views for browse tables, batch DataLoaders, Redis caching, Searchkick async indexing.
- **Key patterns worth adopting**:
  - GraphQL for connected entity traversal
  - Polymorphic concerns (Commentable, Flaggable, Subscribable) on any entity type
  - Revision-based curation with field-level diffs
  - Materialized views for browse/search performance
  - DataLoader batching for N+1 prevention
  - `browseX` queries with faceted filtering + full-text search
  - Activity/audit trail for all state changes

**Alternatives considered**: REST-only (simpler but poor for graph traversal), Hasura auto-generated GraphQL (fast but less control over business logic)

## R2: GraphQL vs REST Decision

**Decision**: GraphQL as primary API, with optional REST endpoints for simple bulk operations (import/export).

**Rationale**:
- The undata data model is highly connected: elements ↔ ontology_annotations ↔ provenance ↔ transforms ↔ schemas ↔ values ↔ valuesets
- GraphQL's nested query resolution eliminates N+1 REST calls when exploring connections
- CivicDB — a directly analogous biomedical curation platform — uses GraphQL successfully
- Faceted search maps naturally to GraphQL arguments
- Cursor-based pagination scales better than offset-based for large datasets
- Mutations model curation workflows cleanly (submitAnnotation, approveFlag, rejectFlag)

**Alternatives considered**:
- REST only: Simpler, but requires many endpoints for relationship traversal; poor fit for graph exploration
- Hybrid REST+GraphQL: Adds complexity of maintaining two API surfaces; GraphQL can handle bulk operations via batch mutations
- Hasura: Auto-generates GraphQL from Postgres; fast setup but limits custom business logic (curation workflows, LLM enrichment triggers)

## R3: Library Code Audit Findings

**Decision**: Extract shared utilities, fix encapsulation, fill test gaps.

**Key findings from code audit**:

### Cross-module private imports (1 occurrence)
- `cli.py` imports `_download_obo` from `ontology_fetch` → make public or wrap

### Dead code
- `Constraints`, `SchemaProvenance`, `ValueProvenance`, `source_attribute`, `source_class` properly removed
- `ontology_term` on `ResponseOption` is valid (per-value link); no dead references remain

### Duplicate patterns needing shared utilities
1. **YAML safe_load with error handling**: 8 unguarded `yaml.safe_load()` calls in `ingest.py`
2. **Filename sanitization**: 3 different approaches across `commit.py`, `ingest.py`
3. **Hardcoded URIs**: 8+ occurrences of `https://schema.undata.live/...` instead of using `build_*_uri()` helpers
4. **Export pagination**: 3-way duplication in `export.py`

### Test gaps (public functions without tests)
- `acquire_source()`, `build_source_ref_from_cache()` (acquisition.py)
- `ontology_search()`, `map_to_skos()` (ontology_store.py)
- `run_workflow()`, `load_workflow()` (workflow.py)
- CLI commands: `export_cmd`, `import_cmd`, `ontology_refresh`
- ~10 public functions total without dedicated tests

## R4: LLM-Assisted Enrichment Strategy

**Decision**: Use LLM as a verification layer for borderline ontology matches (0.7-0.95 cosine similarity).

**Approach**:
1. Embedding similarity identifies candidates (existing pipeline)
2. For borderline matches (0.7-0.95), send to LLM with: element description + candidate ontology term definition + source context
3. LLM returns: confirm/reject + confidence + justification
4. Confirmed matches are auto-assigned; rejected matches are flagged for human curation
5. Use `litellm` (already in optional deps) for model-agnostic LLM access

**Rationale**: LLM verification reduces false positives in enrichment without requiring human review for every borderline case. The justification text becomes part of the curation evidence.

## R5: Modern Stack for UI/DB Rebuild

**Decision**: Python backend (FastAPI + Strawberry GraphQL) + TypeScript frontend (Next.js + Apollo Client) + PostgreSQL

**Rationale**:
- Python backend keeps library integration zero-cost (import directly, no serialization boundary)
- Strawberry is the leading Python GraphQL library (type-safe, Pydantic integration)
- Next.js provides SSR for SEO + app-router for complex navigation
- Apollo Client is the standard GraphQL client with caching and connection management
- PostgreSQL reused from existing infrastructure

**Alternatives considered**:
- Ruby on Rails (CivicDB's choice): Would require rewriting library bindings; Python ecosystem alignment is stronger
- Django + Graphene: Django's ORM is sync-first; FastAPI + SQLAlchemy async is already proven in 002-schema-backend
- SvelteKit: Lighter but smaller ecosystem for complex data-heavy UIs
