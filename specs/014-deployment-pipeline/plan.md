# Implementation Plan: Deployment Pipeline

**Branch**: `014-deployment-pipeline` | **Date**: 2026-03-15 | **Spec**: spec.md

## Summary

GitHub Actions workflows for container image publishing (GHCR), documentation site
deployment (GitHub Pages), and backend integration tests in CI.

## Technical Context

**CI**: GitHub Actions
**Registry**: GitHub Container Registry (ghcr.io/sensein/*)
**Pages**: GitHub Pages (tutorials + meta-model docs)
**Existing**: frontend.yml, lint.yml, tutorials-offline.yml, metamodel-docs.yml

## Constitution Check

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Simplicity | ✅ | 3 new workflows + 1 modified; standard GHA patterns |
| II. TDD | ✅ | backend-tests.yml runs full pytest suite |
| VI. Env Isolation | ✅ | Services run in Docker; tests use service containers |

## Workflow Designs

### build-images.yml (on tag v*)

```yaml
trigger: push tags v*
jobs:
  build-push:
    strategy:
      matrix:
        service: [backend, migration-api, frontend]
    steps:
      - checkout
      - docker/login-action (GHCR)
      - docker/build-push-action (context: ./$service, push: true,
        tags: ghcr.io/sensein/undata-$service:$tag, :latest)
```

### tutorials-site.yml (on push main, paths tutorials/)

```yaml
steps:
  - checkout
  - setup-uv
  - uv sync (tutorials/)
  - uv run jupyter-book build .
  - deploy to gh-pages (publish_dir: tutorials/_build/html)
```

### backend-tests.yml (on PR, paths backend/)

```yaml
services:
  postgres: pgvector/pgvector:pg16 (health: pg_isready)
steps:
  - checkout
  - setup-uv
  - uv sync (backend/)
  - alembic upgrade head
  - pytest tests/ -v
```
