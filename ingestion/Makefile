# Makefile — undata ingestion pipeline
#
# Requirements by target:
#   Requires Docker:    backend-up
#   Requires backend:   backend-wait, ingest-code, ingest-aind, ingest, generate, validate
#   Pure Python:        fetch-schemas, test, lint

SHELL := /bin/bash
BACKEND_URL ?= http://localhost:8002/api/v1
BACKEND_HEALTH = http://localhost:8002/health
BACKEND_WAIT_TIMEOUT ?= 60
OUTPUT ?= unified.yaml

.PHONY: help backend-up backend-wait fetch-schemas ingest-code ingest-aind ingest generate validate pipeline test lint

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
	  awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ── Backend (requires Docker) ─────────────────────────────────────────────────

backend-up:  ## Start backend + db via docker compose (requires Docker)
	docker compose -f ../backend/docker-compose.yml up -d db backend

backend-wait:  ## Wait for backend /health to return 200 (requires backend running)
	@echo "Waiting for backend at $(BACKEND_HEALTH)..."
	@timeout=$(BACKEND_WAIT_TIMEOUT); \
	while [ $$timeout -gt 0 ]; do \
	  if curl -fsSL $(BACKEND_HEALTH) > /dev/null 2>&1; then \
	    echo "Backend is up!"; exit 0; \
	  fi; \
	  sleep 2; timeout=$$((timeout - 2)); \
	done; \
	echo "ERROR: Backend did not respond after $(BACKEND_WAIT_TIMEOUT)s"; exit 1

# ── Schema fetching (pure Python / curl / git) ────────────────────────────────

fetch-schemas:  ## Download full schema fixtures: NWB, openMINDS, AIND, DANDI (idempotent)
	bash scripts/fetch-schemas.sh

# ── Ingestion (requires backend running) ─────────────────────────────────────

ingest-code:  ## Ingest BIDS, DANDI, NWB, openMINDS via code-path (requires backend)
	uv run undata ingest bids dandi nwb openminds --extraction-mode code

ingest-aind:  ## Ingest AIND via file-path (requires backend + schemas/aind/ populated)
	uv run undata ingest aind --extraction-mode file

ingest:  ## Ingest all five sources (code + file paths, requires backend)
	$(MAKE) ingest-code
	$(MAKE) ingest-aind

# ── Schema generation (requires backend running + ingested data) ──────────────

generate:  ## Generate unified LinkML YAML from backend data (requires backend)
	uv run undata generate-schema --output $(OUTPUT)

# ── Validation (pure Python, requires linkml dev dep) ─────────────────────────

validate:  ## Validate unified.yaml with linkml-validate (requires linkml dev dep)
	uv run linkml-validate --schema $(OUTPUT)

# ── Full pipeline ─────────────────────────────────────────────────────────────

pipeline:  ## Run full pipeline: backend-up → wait → fetch-schemas → ingest → generate → validate
pipeline: backend-up backend-wait fetch-schemas ingest generate validate
	@echo "=== Pipeline complete. $(OUTPUT) is valid. ==="

# ── Development ──────────────────────────────────────────────────────────────

test:  ## Run unit tests (pure Python)
	uv run pytest tests/ -q

lint:  ## Run ruff check + format check (pure Python)
	uv run ruff check src/ tests/
	uv run ruff format --check src/ tests/
