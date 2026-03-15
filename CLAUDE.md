# undata Development Guidelines

Auto-generated from all feature plans. Last updated: 2026-03-09

## Active Technologies

- Python 3.14 + uv + FastAPI 0.111+ + SQLAlchemy 2.x async + PostgreSQL 16 + authlib 1.x + cachetools 5.x + pydantic-settings + rdflib 7.x + cmixf 0.2.x (002-schema-backend)
- Python 3.14 + nbmake 1.5+ + ipykernel + jupyter + httpx (009-tutorials)
- Python 3.12 + linkml-runtime 1.8+ + bidsschematools + dandischema + hdmf (001-neuro-schema-integration)
- Python 3.12 + FastAPI 0.111+ + Celery 5.x + Redis 7.x + simpleeval 1.0+ + RestrictedPython 7.x + linkml-runtime 1.8+ + httpx 0.27+ (004-migration-api)
- TypeScript 5.x + Next.js 15.x (React) + Cytoscape.js + shadcn/ui + Meilisearch (003-schema-explorer)
- PostgreSQL 16 + pgvector (002-schema-backend)
- Redis 7.x (004-migration-api async jobs)

## Project Structure

```text
undata/
├── backend/          # 002: Schema backend REST API (Python/FastAPI/PostgreSQL)
├── ingestion/        # 001: Schema ingestion + LinkML generation (Python CLI)
├── migration-api/    # 004: Migration API (Python/FastAPI/Celery)
├── frontend/         # 003: Schema Explorer (SvelteKit/TypeScript)
├── specs/            # Feature specifications and plans
│   ├── 001-neuro-schema-integration/
│   ├── 002-schema-backend/
│   ├── 003-schema-explorer/
│   └── 004-migration-api/
└── docker-compose.yml
```

## Service Ports

| Service | Port |
|---------|------|
| backend (002) | 8002 |
| migration-api (004) | 8004 |
| frontend (003) | 5173 (dev) |
| Keycloak (002 IdP) | 8080 |
| PostgreSQL | 5432 |
| Redis | 6379 |

## Commands

```bash
# Start all services
docker compose up -d

# Backend tests
cd backend && pytest tests/ -v

# Ingestion tool
cd ingestion && undata ingest bids dandi openminds nwb

# Generate LinkML schema
cd ingestion && undata generate-schema --output unified.yaml

# Migration API tests
cd migration-api && pytest tests/ -v

# Frontend dev server
cd frontend && pnpm dev     # Next.js dev server at http://localhost:3000

# Frontend tests
cd frontend && pnpm test && pnpm exec playwright test

# Index elements in Meilisearch (run after backend is populated)
cd frontend && pnpm run index-elements
```

## Code Style

```
Python: ruff format + ruff check (pyproject.toml), type hints required
TypeScript: strict mode, eslint + prettier
```

## Dependency Order

```
002-schema-backend   ← foundational (all others depend on this)
001-neuro-integration ← populates backend; depends on 002
004-migration-api    ← depends on 002; extends backend with /pathways + /schemas
003-schema-explorer  ← depends on 002 + 004
```

## Recent Changes

- 008-schema-import-roundtrip: PLANNING — GenericJSONSchemaAdapter (any draft-07/2019/2020 JSON Schema → NormalizedElements); LinkMLAdapter (LinkML YAML → NormalizedElements); roundtrip_json_schema() + roundtrip_linkml() → RoundtripResult; CLI `undata roundtrip`; no new prod deps; offline only
- 007-end-to-end-pipeline: IN PROGRESS — pynwb+openMINDS added to pyproject.toml (v2026.03.2); BIDSAdapter loads all 9 vocabulary types (≥1012 elements) with sidecar-based class groups; DANDIAdapter extracts $defs + self-ref model fallback; NWBAdapter traverses multi-file namespace manifests; LinkML generator Pass 2 emits DynamicSchema is_a/mixin/mixins; 409 DuplicateSourceError → WARN+continue; fetch-schemas.sh + Makefile pipeline
- 009-tutorials: COMPLETE — 7 notebooks in tutorials/; nbmake for pytest execution; offline T06; auto-skip via conftest.py pytest_collection_modifyitems hook (reads undata.services_required metadata); all notebooks pass ruff check
- 008-schema-import-roundtrip: COMPLETE — GenericJSONSchemaAdapter (any draft-07/2019/2020 JSON Schema), LinkMLAdapter (linkml_runtime yaml_loader), roundtrip_json_schema()/roundtrip_linkml() fidelity functions, RoundtripResult dataclass, `undata roundtrip` CLI subcommand; 46 new tests (192 total pass)
- 006-dual-path-adapters: IN PROGRESS — all 5 adapters gain load_code()/load_file() dual-path methods; ExtractionMode ("code"|"file"|"both"); merge+dedup with WARN/ERROR logging; SchemaClassPayload.extraction_path → "code"/"file"/"both" + new schema_format field; CLI --extraction-mode + --source-path flags
- 005-schema-enrichment: COMPLETE — dual-path class extraction (json/yaml/jsonld/code), ValidationRule breaking-change classifier (6 rule types), C3 MRO linearization + cycle detection, SchemaChangeLog PROV-DM JSON-LD provenance, ProvenanceMixin system schema, cascade soft-delete; 5 ingestion adapters extended with extract_classes(); migrations 0004–0009
- 002-schema-backend: Added unit standardization — cmixf-12 symbol validation + QUDT ontology URI resolution (auto-enriches semantic_graph.unit with external_uri, cmixf_valid, qudt_unresolvable); new GET /units and GET /units/unresolvable endpoints; UnitResolutionService singleton loaded at startup from bundled QUDT v3.1.x TTL
- 002-schema-backend: Added persistent URI scheme (UNDATA_BASE_URL/{type}/{uuid}), DynamicSchema entity with URI, DataElementChild nesting, actor_id UUID FK in AuditLog
- 002-schema-backend: Added authlib + Keycloak OIDC federation (Globus/GitHub/InCommon) + RBAC+ReBAC authz + API key token model + on-demand alias detection endpoint
- 002-schema-backend: Added Python 3.12 + FastAPI + PostgreSQL 16
- 001-neuro-schema-integration: Added linkml-runtime + 4 schema adapters
- 004-migration-api: Added Celery + Redis + simpleeval migration execution

<!-- MANUAL ADDITIONS START -->
<!-- Last updated: 2026-03-09 by update-agent-context.sh (branch: 001-neuro-schema-integration) -->
<!-- Last updated: 2026-03-09 by update-agent-context.sh (branch: 005-schema-enrichment) -->
<!-- Last updated: 2026-03-10 by update-agent-context.sh (branch: 005-schema-enrichment) -->
<!-- Last updated: 2026-03-11 by update-agent-context.sh (branch: 007-end-to-end-pipeline) -->
<!-- Last updated: 2026-03-11 by update-agent-context.sh (branch: 008-schema-import-roundtrip) -->
<!-- Last updated: 2026-03-11 by update-agent-context.sh (branch: 009-tutorials) -->
<!-- Last updated: 2026-03-12 by update-agent-context.sh (branch: 011-metamodel-provenance) -->
<!-- Last updated: 2026-03-13 by update-agent-context.sh (branch: 011-metamodel-provenance) -->
<!-- Last updated: 2026-03-15 by update-agent-context.sh (branch: 015-undata-library) -->
<!-- MANUAL ADDITIONS END -->
