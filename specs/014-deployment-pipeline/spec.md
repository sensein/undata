# Feature Specification: Deployment Pipeline

**Feature Branch**: `014-deployment-pipeline`
**Created**: 2026-03-15
**Status**: Draft
**Input**: CI/CD workflows for building, testing, and publishing container images + static sites.

---

## Overview

Add GitHub Actions workflows for:
1. Building and pushing Docker images to GitHub Container Registry (GHCR) on tag
2. Publishing the JupyterBook tutorials site to GitHub Pages
3. Publishing the meta-model docs to GitHub Pages (extends existing workflow)
4. Running backend integration tests in CI

---

## User Scenarios & Testing

### User Story 1 — Publish Container Images (Priority: P1)

A maintainer tags a release and Docker images are automatically built and pushed to GHCR.

**Acceptance Scenarios**:

1. **Given** a push to `v*` tag, **When** CI runs, **Then** `ghcr.io/sensein/undata-backend`,
   `ghcr.io/sensein/undata-migration-api`, and `ghcr.io/sensein/undata-frontend` images
   are pushed with the tag version + `latest`.
2. **Given** images are pushed, **When** a user pulls them, **Then** they start correctly
   with the documented environment variables.

### User Story 2 — Publish Documentation Sites (Priority: P1)

A maintainer pushes to `main` and documentation sites are automatically built and deployed.

**Acceptance Scenarios**:

1. **Given** a push to `main` modifying `tutorials/`, **When** CI runs, **Then** JupyterBook
   site is built and deployed to GitHub Pages under `/tutorials/`.
2. **Given** a push to `main` modifying `docs/`, **When** CI runs, **Then** meta-model docs
   are built and deployed to GitHub Pages under `/meta/`.

### User Story 3 — Backend Integration Tests in CI (Priority: P2)

Backend tests run automatically on PRs touching `backend/`.

**Acceptance Scenarios**:

1. **Given** a PR modifying `backend/`, **When** CI runs, **Then** PostgreSQL service is
   started, migrations applied, and `pytest` runs all tests.

---

## Requirements

### Functional Requirements

- **FR-001**: `build-images.yml` MUST build and push 3 images to GHCR on `v*` tags.
- **FR-002**: `tutorials-site.yml` MUST build JupyterBook and deploy to GitHub Pages.
- **FR-003**: `metamodel-docs.yml` (existing) MUST be updated to deploy under `/meta/`.
- **FR-004**: `backend-tests.yml` MUST spin up PostgreSQL and run pytest on PR.
- **FR-005**: All workflows MUST use `actions/checkout@v4` and cache dependencies.

### Non-Functional Requirements

- **NFR-001**: Image builds MUST complete in under 10 minutes.
- **NFR-002**: Backend test CI MUST complete in under 5 minutes.

### Key Entities

- `.github/workflows/build-images.yml`
- `.github/workflows/tutorials-site.yml`
- `.github/workflows/backend-tests.yml`
- `.github/workflows/metamodel-docs.yml` (modified)

---

## Success Criteria

- **SC-001**: Tagged release produces 3 GHCR images.
- **SC-002**: JupyterBook site deployed to GitHub Pages on push to main.
- **SC-003**: Backend tests run and report status on PRs.
