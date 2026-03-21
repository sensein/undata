<!--
SYNC IMPACT REPORT
==================
Version change: 1.2.1 → 1.3.0
Bump rationale: MINOR — new "Git Commit Discipline" subsection added to the
  Development Workflow section. Materially expanded guidance requiring the agent
  to commit every meaningful unit of work and leave no uncommitted changes at
  session end.

Modified principles: None renamed.

Added sections:
  - Development Workflow > Git Commit Discipline (new subsection)

Removed sections: None

Templates requiring updates:
  - .specify/templates/plan-template.md  ✅ No changes required.
  - .specify/templates/spec-template.md  ✅ No changes required.
  - .specify/templates/tasks-template.md ✅ No changes required.
  - .specify/templates/agent-file-template.md  ✅ No changes required.
  - .specify/templates/checklist-template.md   ✅ No changes required.
  - CLAUDE.md (root agent file)  ✅ No changes required; rule is agent-session
    behaviour, not a project technology baseline.

Deferred TODOs: None.
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

**Bridge Venv Exception** — third-party schema library evaluation:

When an ingestion adapter must introspect a third-party schema library that
does not yet support Python 3.14 (e.g., `aind-data-schema`, `openminds-python`,
`hdmf`/`pynwb`), a separate, purpose-built virtual environment (a "bridge venv")
using an earlier Python version MAY be created solely for that evaluation.
The following rules MUST all be satisfied for the exception to apply:

1. **uv-managed**: The bridge venv MUST be created and managed by `uv`
   (e.g., `uv venv --python 3.12 .venv-bridge-<name>`).
2. **Subprocess-only access**: All interaction with the bridge venv MUST be via
   subprocess call or a defined inter-process interface (e.g., a helper script
   that prints JSON to stdout). Direct import of bridge-venv packages into the
   main Python 3.14 process is prohibited.
3. **No first-party code**: Bridge venvs MUST NOT contain any first-party
   undata source packages. They exist only to invoke third-party library APIs
   and return serializable data.
4. **Separate requirements file**: Bridge venv dependencies MUST be declared in
   a clearly named, separate file (e.g., `pyproject-bridge-<name>.toml` or
   `requirements-bridge-<name>.txt`) committed alongside the adapter. The main
   `pyproject.toml` `requires-python` MUST remain `>=3.14`.
5. **Serializable output only**: Data produced by a bridge venv script MUST be
   representable as JSON (or another format readable by standard Python 3.14
   builtins) so no bridge-venv types cross the process boundary.
6. **Documented in plan**: Any feature that introduces a bridge venv MUST
   document it explicitly in the plan's Technical Context and Constitution Check
   sections, citing this exception.

**Rationale**: Reproducible, isolated environments eliminate "works on my
machine" failures, prevent accidental system-Python contamination, and ensure
CI/CD and local developer runs execute against identical dependency graphs.
The bridge venv exception acknowledges real-world library adoption lag while
preserving the 3.14+ baseline for all first-party development and preventing
silent fallbacks or mixed-interpreter contamination.

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

### Git Commit Discipline

Every meaningful unit of work MUST be committed to git before the session ends.
The following rules are NON-NEGOTIABLE:

- **Commit per task**: Each completed task (or logical group of closely related
  changes) MUST result in a git commit before moving to the next task.
- **No dangling changes**: The agent MUST NOT leave uncommitted file modifications,
  additions, or deletions at the end of a work session. `git status` MUST show a
  clean working tree before the session is considered complete.
- **Push after commit**: Changes MUST be pushed to the remote repository after
  committing, unless the user explicitly instructs otherwise.
- **Commit message quality**: Commit messages MUST follow the project's established
  style (imperative mood, concise subject line, co-author trailer for AI-assisted
  commits). They MUST accurately describe what changed and why.
- **Staged content**: Only intentional changes MUST be staged. The agent MUST
  review `git status` and `git diff --staged` before committing to confirm no
  unintended files (e.g. secrets, build artifacts, OS files) are included.

**Rationale**: Uncommitted changes are invisible to collaborators, cannot be
reviewed or reverted atomically, and are at risk of being lost. Committing per
task creates an auditable, recoverable history that mirrors the speckit lifecycle
and supports parallel work across branches.

### Evaluation Record

Pipeline runs, extraction results, and quality metrics MUST be recorded in
`eval-record.md` at the repository root. The following rules apply:

- **Record after extraction**: Every significant re-extraction or pipeline run
  MUST append a dated section to `eval-record.md` with: source counts, entity
  counts, ontology term counts, transform counts, enrichment rates, known
  issues, and performance timings.
- **Record from any source**: Results from chat outputs, CLI runs, CI pipelines,
  or manual testing MUST all be captured in `eval-record.md` — not only in
  commit messages or conversation context.
- **Quantitative and qualitative**: Each record MUST include both numbers
  (element count, ontology assignment rate) and qualitative notes (known issues,
  what changed from previous run, what to investigate).
- **Baseline comparison**: When recording new results, note significant changes
  from the previous record (e.g., "element count increased from 7,756 to 14,114
  due to enrichment creating new elements with ontology_term").

**Rationale**: Extraction results are the primary evidence that the pipeline is
working correctly. Without a persistent record, regressions go undetected and
progress is invisible. Commit messages capture intent; `eval-record.md` captures
outcomes.

### Bash Task Hygiene

Every bash command the agent runs MUST be verified for completion and its result
acted upon or explicitly dismissed.

- **Background tasks**: A task launched with `run_in_background` MUST be stopped
  (via `TaskStop` or equivalent) as soon as its result is obtained or the task is
  no longer needed. Background tasks MUST NOT be left running across conversation
  turns once their purpose is fulfilled.
- **Foreground tasks**: The exit code and output of every foreground bash command
  MUST be checked before proceeding. A non-zero exit code MUST be investigated,
  not silently ignored.
- Tasks that become redundant mid-session (e.g., superseded by a code fix or a
  later command) MUST be stopped or their output explicitly discarded with a
  logged reason.
- At the end of any implementation session the agent MUST confirm no background
  tasks remain running.

**Rationale**: Unverified commands and abandoned tasks leave the session in an
unknown state, produce confusing notifications in future sessions, and indicate
that the agent has lost track of its own work. Rigorous task hygiene is a
prerequisite for reliable, auditable agent-assisted development.

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

**Version**: 1.4.0 | **Ratified**: 2026-03-07 | **Last Amended**: 2026-03-21
