<!--
SYNC IMPACT REPORT
==================
Version change: 1.0.1 → 1.1.0
Bump rationale: MINOR — new Principle VI added; Technology & Quality Standards
  section fully populated (replacing the TODO(TECH_STACK) placeholder).

Modified principles: None (existing I–V unchanged)
Added sections:
  - Principle VI: Environment Isolation & Reproducibility (new)
  - Technology & Quality Standards fully filled (was TODO placeholder)

Removed sections: None

Templates requiring updates:
  - .specify/templates/plan-template.md  ✅ No changes required; Constitution
    Check section is generic and remains valid.
  - .specify/templates/spec-template.md  ✅ No changes required; mandatory
    sections align with all six principles.
  - .specify/templates/tasks-template.md ✅ No changes required; phase
    structure and test-optional policy align with Principle II; environment
    setup tasks already included in Phase 1 (Setup) guidance.
  - .specify/templates/agent-file-template.md  ✅ No changes required;
    template is fully generic.
  - .specify/templates/checklist-template.md   ✅ No changes required.
  - CLAUDE.md (root agent file)  ✅ Already reflects Python 3.14 + uv venv
    conventions established in 002-schema-backend implementation.

Deferred TODOs: None — all TODOs resolved in this revision.
-->

# undata Constitution

## Core Principles

### I. Simplicity First

Every design decision MUST default to the simplest solution that satisfies the
requirement. Complexity MUST be justified in writing before it is introduced.
YAGNI (You Aren't Gonna Need It) applies at all levels: no speculative
abstractions, no premature generalization, no optional configurability without
a concrete use case.

**Rationale**: Complexity is the primary source of defects and maintenance
burden. A simple codebase is more auditable, easier to onboard, and faster
to change.

### II. Test-Driven Development (NON-NEGOTIABLE)

Tests MUST be written before implementation code. The Red-Green-Refactor cycle
MUST be strictly enforced:

1. Write a failing test that captures the requirement.
2. Obtain explicit approval that the test correctly expresses intent.
3. Implement only enough code to make the test pass.
4. Refactor under green.

Tests are OPTIONAL in generated task lists only when the feature specification
explicitly opts out. When tests are included, they MUST fail before any
implementation task begins.

**Rationale**: TDD provides living documentation, catches regressions early,
and enforces a tight feedback loop between requirements and code.

### III. API-First Design

Every module or service boundary MUST define its contract (interface, schema,
or CLI protocol) before implementation begins. Contracts are versioned
artifacts stored under `specs/[feature]/contracts/`. Internal implementation
details MUST NOT leak across boundaries.

**Rationale**: Explicit contracts enable independent development, parallel
testing, and safe evolution of components without hidden coupling.

### IV. Observability

All runtime paths that handle user-facing operations MUST emit structured,
machine-readable logs (JSON preferred). Log levels MUST be used consistently:
`ERROR` for actionable failures, `WARN` for degraded-but-continuing states,
`INFO` for significant lifecycle events, `DEBUG` for developer diagnostics.
Silent failures are prohibited.

**Rationale**: Systems that cannot be observed cannot be reliably operated or
debugged in production.

### V. Versioning & Stability

Public interfaces MUST follow Calendar Versioning (CalVer) using the format
`YYYY.MM.MICRO`, where `YYYY` is the four-digit year, `MM` is the two-digit
month, and `MICRO` is a zero-based release counter reset each month
(e.g., `2026.03.0`, `2026.03.1`). Breaking changes MUST be accompanied by a
migration guide documented before the change is merged. Deprecated interfaces
MUST be marked and retained for at least one calendar-month release cycle
before removal.

**Rationale**: CalVer communicates the release timeline directly in the
version string, making it easy to assess freshness and coordinate upgrades
in time-aware workflows.

### VI. Environment Isolation & Reproducibility

All Python work MUST run inside a virtual environment. The following rules are
NON-NEGOTIABLE:

- `uv` MUST be used for all Python dependency management (installation,
  locking, running tools).
- Python MUST NEVER be invoked via the system interpreter for project work;
  use `uv run <cmd>` locally or activate the project venv.
- Docker images MUST create an explicit venv (`uv venv`) and install into it
  (`uv pip install --python <venv>`); `--system` installs are prohibited.
  Set `ENV PATH` and `ENV VIRTUAL_ENV` so all subsequent image layers and
  runtime processes use the venv automatically.
- The `pyproject.toml` `requires-python` constraint MUST pin to the project's
  tested interpreter (currently `>=3.14`).
- All services and test runners in Docker Compose MUST reference the venv
  binary explicitly (e.g., `/app/.venv/bin/python`) or rely on the venv being
  activated via `ENV PATH`.

**Rationale**: Reproducible, isolated environments eliminate "works on my
machine" failures, prevent accidental system-Python contamination, and ensure
CI/CD and local developer runs execute against identical dependency graphs.

## Technology & Quality Standards

### Runtime & Toolchain

| Concern | Canonical Choice |
|---|---|
| Language | Python 3.14 (`requires-python = ">=3.14"`) |
| Package manager | `uv` (always via venv — see Principle VI) |
| Web framework | FastAPI 0.111+ with async route handlers |
| ORM | SQLAlchemy 2.x async (`AsyncSession`) |
| Migrations | Alembic (async env.py; `-x url=` flag for test overrides) |
| Database | PostgreSQL 16 + pgvector extension |
| Auth / IdP | Keycloak 24+ (OIDC); `authlib` 1.x for token handling |
| Containerisation | Docker + Docker Compose; venv inside image (Principle VI) |
| Ontology / vocab | `rdflib` ≥ 7.0 for RDF/TTL; QUDT unit vocabulary bundled |
| Unit validation | `cmixf` ≥ 0.2 (regex-based symbol validation) |

### Testing Standards

- **Framework**: `pytest` + `pytest-asyncio` (mode `auto`); `pytest.ini`
  MUST be copied into Docker images to ensure consistent asyncio mode.
- **Alembic in tests**: Run via `subprocess` (not Python API) to avoid
  `asyncio.run()` conflicts with the pytest-asyncio event loop. Pass the test
  URL via `-x url=<TEST_DATABASE_URL>`.
- **Test database**: A dedicated `undata_test` database MUST exist; created
  via `postgres-init/` init scripts on fresh Postgres containers.
- **Lifespan bypass**: `httpx.ASGITransport` does NOT trigger FastAPI
  lifespan. Session-scoped fixtures MUST replicate lifespan side-effects
  (unit-service init, undata source seeding) for tests.
- **Layers**: Unit tests (`tests/unit/`), contract tests
  (`tests/contract/`), integration tests (`tests/integration/`). Each layer
  MUST be independently runnable.
- **Coverage**: All new services and API endpoints MUST have contract tests.
  Unit tests required for pure-logic modules (services, utilities).

### Linting & Formatting

- `ruff check` and `ruff format` MUST pass on every commit (configured in
  `pyproject.toml`).
- Maximum line length: 100 characters.
- `ruff` is the sole formatter and linter; no additional tools (no `black`,
  no `flake8`).

### Performance Envelopes

- API p95 response time: < 500 ms for read endpoints under typical load.
- Embedding generation (sentence-transformers): acceptable at startup; MUST
  NOT block request handling (called only during element create/update).
- QUDT TTL load time: < 3 s at startup (2,896 units, ~60k triples observed).

## Development Workflow

All work MUST flow through the speckit lifecycle:

1. **Specify** (`/speckit.specify`): Capture user stories and acceptance
   criteria before any design or code.
2. **Plan** (`/speckit.plan`): Research, data model, contracts, and
   implementation approach agreed before tasks are generated.
3. **Tasks** (`/speckit.tasks`): Dependency-ordered task list derived from
   spec and plan. Tasks grouped by user story to support incremental delivery.
4. **Implement** (`/speckit.implement`): Execute tasks sequentially or in
   declared parallel groups. No skipping ahead; no undeclared changes outside
   the active task scope.
5. **Analyze** (`/speckit.analyze`): Cross-artifact consistency check before
   marking a feature complete.

Pull requests MUST reference the corresponding spec and pass all tests and
linting gates before merge. Complexity violations flagged in the plan's
Complexity Tracking table MUST be resolved or explicitly carried forward with
a documented justification.

## Governance

This constitution supersedes all other project practices. Any practice not
addressed here defaults to the principle of Simplicity First (Principle I).

**Amendment procedure**:

1. Propose the change in writing, citing the principle or governance rule
   affected and the rationale for the change.
2. Update this file with the amended content.
3. Increment the version number per the semantic versioning rules below.
4. Propagate changes to all dependent templates and agent guidance files.
5. Record the amendment in a commit message referencing the new version.

**Versioning policy** (this constitution document uses SemVer internally):

- MAJOR: Removal or redefinition of an existing principle in a
  backward-incompatible way.
- MINOR: Addition of a new principle or materially expanded guidance.
- PATCH: Clarifications, wording improvements, typo fixes.

Project releases MUST use CalVer `YYYY.MM.MICRO` as defined in Principle V.

**Compliance review**:

All PRs and implementation plans MUST include a Constitution Check section
confirming compliance with active principles. Violations require documented
justification or the work is blocked.

**Version**: 1.1.0 | **Ratified**: 2026-03-07 | **Last Amended**: 2026-03-09
