# Implementation Plan: Library Hardening, Pipeline Optimization, UI/DB Rebuild

**Branch**: `027-library-hardening-pipeline` | **Date**: 2026-03-22 | **Spec**: [spec.md](spec.md)

## Summary

Three-workstream feature: (1) Audit and clean up the library codebase — shared utilities, encapsulation, test coverage; (2) Optimize every pipeline step for accuracy using embeddings + LLM verification + ontology hierarchy, add curation flags and run summaries; (3) Rebuild UI/DB from scratch inspired by CivicDB — GraphQL API, social curation (contributors + curators), connected entity navigation.

## Technical Context

**Language/Version**: Python 3.14 (library + backend), TypeScript 5.x (frontend)
**Primary Dependencies**:
- Library: pydantic, pyarrow, sentence-transformers, pyoxigraph, litellm, python-dotenv
- Backend: FastAPI, Strawberry (GraphQL), SQLAlchemy 2.x async, PostgreSQL 16
- Frontend: Next.js 15, Apollo Client, Tailwind CSS
**Storage**: PostgreSQL 16 (backend DB), flat-file YAML (library registry), pyoxigraph (ontology store)
**Testing**: pytest (library + backend), Playwright (frontend + CivicDB study)
**Target Platform**: Linux/macOS server, web browser
**Project Type**: Library + CLI + web application (full stack)
**Performance Goals**: GraphQL queries < 500ms p95, curation queue < 2s load, incremental import < 60s
**Constraints**: Not a deployed platform — can rewrite anything from scratch. Accuracy over cost/latency.
**Scale/Scope**: ~7,700 elements, 642 schemas, 1,000 values, 86 valuesets, 268K ontology terms

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity First | PASS | Three workstreams are sequential, not parallel complexity. Each stands alone. |
| II. TDD | PASS | Every workstream ends with full pipeline re-extraction test. US1 adds edge-case tests. |
| III. API-First | PASS | GraphQL contract defined before implementation (contracts/graphql-schema.md). |
| IV. Observability | PASS | RunSummary entity provides structured machine-readable pipeline logs. |
| V. Versioning | PASS | CalVer continues. Not deployed — no deprecation needed. |
| VI. Environment Isolation | PASS | uv for all Python. Isolated venvs for source adapters. |
| Secret Handling | PASS | dotenv for HF_TOKEN and LLM API keys. Never inline. |
| Git Commit Discipline | PASS | Commit per task, push after commit. |
| Evaluation Record | PASS | Pipeline runs update eval-record.md with comparison. |

## Project Structure

### Documentation

```text
specs/027-library-hardening-pipeline/
├── plan.md
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── graphql-schema.md
│   └── cli-pipeline.md
└── tasks.md
```

### Source Code

```text
library/                          # US1 + US2: cleanup + pipeline optimization
├── src/undata_library/
│   ├── utils.py                  # NEW: shared utilities (safe_load_yaml, sanitize_filename, etc.)
│   ├── curation.py               # NEW: CurationFlag model + curation queue management
│   ├── run_summary.py            # NEW: RunSummary generation + delta comparison
│   ├── llm_enrich.py             # NEW: LLM-assisted verification for borderline matches
│   ├── models.py                 # MODIFIED: add CurationFlag, RunSummary models
│   ├── enrich.py                 # MODIFIED: integrate LLM verification + flag generation
│   ├── ingest.py                 # MODIFIED: use shared utils, improve error handling
│   ├── commit.py                 # MODIFIED: use shared utils
│   ├── cli.py                    # MODIFIED: add curation-queue, resolve-flag commands
│   └── adapters/                 # MODIFIED: source-aware validation, change detection
└── tests/
    ├── test_utils.py             # NEW: shared utility tests
    ├── test_curation.py          # NEW: curation flag tests
    ├── test_run_summary.py       # NEW: run summary tests
    ├── test_llm_enrich.py        # NEW: LLM verification tests
    └── test_pipeline_e2e.py      # NEW: full end-to-end pipeline test

backend/                          # US3: rebuilt from scratch
├── src/
│   ├── schema.py                 # Strawberry GraphQL schema
│   ├── resolvers/                # Query + mutation resolvers
│   ├── models/                   # SQLAlchemy models
│   ├── services/                 # Business logic (import, curation)
│   └── db.py                     # Database connection + migrations
└── tests/

frontend/                         # US3: rebuilt from scratch
├── src/
│   ├── app/                      # Next.js app router pages
│   ├── components/               # Reusable UI components
│   ├── graphql/                  # Apollo Client queries + mutations
│   └── lib/                      # Utilities
└── tests/
```

**Structure Decision**: Extend existing `library/` for US1+US2. Rebuild `backend/` and `frontend/` from scratch for US3 (current code doesn't match CivicDB-inspired architecture). Three independent codebases with clear boundaries: library (flat-file), backend (GraphQL+DB), frontend (Next.js).

## Workstream Phases

### Workstream 1: Library Code Review and Cleanup (US1)

**Phase 1.1**: Consolidated requirements audit
- Read all specs 001-026, map user stories to implementation status
- Document what's implemented, partially implemented, or outdated

**Phase 1.2**: Shared utilities extraction
- Create `utils.py`: `safe_load_yaml()`, `sanitize_filename()`, `write_yaml()`, `BASE_URI` constant
- Replace all duplicated patterns across modules
- Make `_download_obo` public or wrap it

**Phase 1.3**: Encapsulation + dead code cleanup
- Fix cross-module private imports
- Remove all dead branches, obsolete comments
- Verify no references to removed models

**Phase 1.4**: Test coverage gap closure
- Add tests for all untested public functions (~10 functions)
- Add edge-case tests (empty inputs, malformed YAML, Unicode, missing fields)
- Add full pipeline end-to-end test

**Phase 1.5**: Re-extraction validation
- Run full pipeline for all 5 sources
- Compare against 026 baseline
- Update eval-record.md

### Workstream 2: Pipeline Optimization (US2)

**Phase 2.1**: LLM-assisted enrichment
- Create `llm_enrich.py` with borderline match verification via litellm
- Integrate into `enrich.py` enrichment pipeline
- Add curation flags for unresolved matches

**Phase 2.2**: Curation flag infrastructure
- Create `curation.py`: CurationFlag model, flag generation, queue management
- Update enrichment to generate flags for borderline/ambiguous matches
- Update transforms to flag "unknown" function types
- CLI commands for curation queue viewing and flag resolution

**Phase 2.3**: Run summary + delta detection
- Create `run_summary.py`: generate run report, compare with previous
- Detect new/modified/removed entities on re-extraction
- Source version tracking (committish comparison)

**Phase 2.4**: Adapter accuracy review
- Read through each source's raw schema format documentation
- Verify each adapter captures all entity types completely
- Document source → undata mapping for each adapter
- Add source-aware change detection

**Phase 2.5**: Re-extraction validation with flags
- Full pipeline with LLM enrichment + curation flags
- Verify flag counts, LLM verification results
- Compare enrichment rate improvements
- Update eval-record.md

### Workstream 3: UI/DB Rebuild (US3)

**Phase 3.1**: CivicDB study
- Playwright exploration of civicdb.org (browse, search, curate flows)
- Code review of griffithlab/civic-v2 (data model, GraphQL schema, social features)
- Document patterns to adopt

**Phase 3.2**: Database schema + GraphQL API
- PostgreSQL schema for elements, schemas, values, transforms, flags, contributions, users
- Strawberry GraphQL schema (queries, mutations, subscriptions)
- Import service: flat-file registry → database

**Phase 3.3**: Frontend — element browser
- Next.js app with Apollo Client
- Faceted search (source, data_type, ontology, curation status)
- Connected entity navigation (element → transforms → schemas)

**Phase 3.4**: Frontend — curation workflows
- Curation queue with evidence panels
- Approve/reject/defer flags
- Contributor submission flow
- User roles (contributor, curator)

**Phase 3.5**: End-to-end validation
- Full pipeline → DB import → UI browse → curate → verify
- Performance testing (query latency, page load)
- Update eval-record.md

## Complexity Tracking

No constitution violations requiring justification. GraphQL adds complexity over REST but is justified by the connected data model (see research.md R2).
