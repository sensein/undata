# Feature Specification: Staged Enrichment Pipeline

**Feature Branch**: `026-staged-enrichment`
**Created**: 2026-03-21
**Status**: Draft
**Input**: New elements should be staged, enriched, and then committed to the registry. Enriching should not create new elements. Ontology annotations, value_domain, and other enrichment metadata are NOT part of the identity hash — they are provenance/metadata that gets added in-place to staged elements before committing.

## User Scenarios & Testing

### User Story 1 — Staged Pipeline: Extract → Enrich → Commit (Priority: P1)

A data curator runs the pipeline and elements flow through three stages: (1) extraction produces staged elements with semantic identity only, (2) enrichment adds ontology annotations, value_domain, and resolved values in-place without changing the element's identity hash or creating new elements, (3) commit finalizes the elements into the registry. No element duplication occurs.

**Why this priority**: The current enrichment creates new elements when ontology_term is assigned (because ontology_term is in the identity hash). This doubles the element count (7,756 → 14,114) with derived copies that share the same concept. The registry should contain one element per unique semantic identity, enriched with metadata.

**Independent Test**: Run the full pipeline. Verify element count after enrichment equals element count after extraction (no new elements created by enrichment).

**Acceptance Scenarios**:

1. **Given** 7,756 elements are extracted, **When** enrichment runs, **Then** exactly 7,756 elements exist afterward (no new elements created).
2. **Given** an element is enriched with ontology annotations, **When** its sha256 is recomputed, **Then** the hash is unchanged (annotations are not in the identity hash).
3. **Given** enrichment assigns `ontology_annotations` and `value_domain`, **When** the element YAML is read, **Then** the annotations appear alongside the semantic block but the sha256 matches the original.
4. **Given** enrichment resolves response_options to ValueConcept URIs, **When** the element is read, **Then** the resolution is recorded in annotations/metadata, not by modifying response_options in the semantic identity.

---

### User Story 2 — ontology_term Removed from Identity Hash (Priority: P1)

The `ontology_term` field is moved out of the identity hash. An element's identity is determined solely by its structural properties (data_type, unit, constraints, min_value, max_value, response_options, source_attribute, source_class, type_ref). Ontology alignment is enrichment metadata, not identity.

**Why this priority**: This is the root cause of enrichment creating new elements. When ontology_term is in the hash, assigning it changes the identity → new element. Moving it out means enrichment is purely additive metadata, never identity-changing.

**Independent Test**: Create two elements differing only in ontology_term. Verify they have the same sha256 hash.

**Acceptance Scenarios**:

1. **Given** element A has `ontology_term: null` and element B has `ontology_term: NCIT:C25150`, **When** both have the same data_type/unit/constraints, **Then** they produce the same sha256 hash (ontology_term excluded).
2. **Given** the existing registry has elements with ontology_term in the hash, **When** migration runs, **Then** elements are rehashed without ontology_term and duplicates are merged.

---

### User Story 3 — Enrichment Updates In-Place (Priority: P1)

Enrichment modifies elements in-place (adding ontology_annotations, value_domain, resolved values) without creating new files or derived_from chains. The enrichment provenance is recorded as a provenance entry on the existing element, not on a new element.

**Why this priority**: In-place enrichment is simpler, produces no element proliferation, and makes the registry easier to reason about. One element = one file = one identity, enriched over time.

**Independent Test**: Enrich an element, verify the same file was updated (not a new file created), and the sha256 is unchanged.

**Acceptance Scenarios**:

1. **Given** element `age_abc123.yaml` exists, **When** enrichment adds ontology_annotations, **Then** the same file `age_abc123.yaml` is updated in-place with the annotations.
2. **Given** enrichment runs, **When** a provenance entry is added, **Then** it has `activity: enrichment` and `attributed_to: urn:undata:enrichment-pipeline` — appended to the existing provenance list.
3. **Given** enrichment runs twice, **When** the second run finds no changes, **Then** no modifications are made (idempotent).

---

### User Story 4 — Commit Stage Rehashes and Finalizes (Priority: P1)

After enrichment, the commit stage computes the final content-addressed hash of each element, writes it to the registry under its final filename, and deletes the staged version. Staged elements carry a pipeline run ID and are ephemeral — only the final committed element persists. No provenance for intermediate pipeline stages.

**Why this priority**: Staged elements are working copies. The registry should only contain finalized, content-addressed entities. Keeping staged intermediates would pollute the registry with temporary files.

**Acceptance Scenarios**:

1. **Given** a staged element with pipeline run ID, **When** commit runs, **Then** the element is rehashed from its final semantic content, written to `elements/{name}_{hash}.yaml`, and the staged copy is deleted.
2. **Given** two staged elements that produce the same final hash, **When** committed, **Then** they merge (provenance combined) into a single registry file.
3. **Given** the pipeline is interrupted before commit, **When** restarted, **Then** staged elements from the incomplete run are cleaned up.

---

### Edge Cases

- What if an element already has ontology_annotations from a prior enrichment? Replace with the new annotations (enrichment is not cumulative across runs — it's a snapshot of the current ontology alignment).
- What if ontology_term was previously in the identity hash and existing elements have different hashes because of it? Migration rehashes all elements without ontology_term; duplicates (same structural identity) are merged with combined provenance.
- What about future curation that intentionally changes identity? Curation is a separate activity type that CAN create new elements (with derived_from). Enrichment never does.
- What if the pipeline crashes between enrich and commit? Staged elements are in a separate staging directory; the registry is untouched until commit.

## Requirements

### Functional Requirements

**Identity Hash Changes**

- **FR-001**: `ontology_term` MUST be removed from the identity hash. It MUST be added to `_EXCLUDED_FROM_HASH` alongside `question_text`, `value_domain`, and `ontology_annotations`.
- **FR-002**: The identity hash MUST be determined solely by: `data_type`, `unit`, `constraints` (pattern + allowed_values only), `min_value`, `max_value`, `response_options` (sorted by value), `source_attribute`, `source_class`, `type_ref`.
- **FR-003**: Existing elements MUST be rehashed after the change. Elements that become duplicates (same hash after ontology_term exclusion) MUST be merged — provenance entries combined, one file retained.

**Staged Pipeline**

- **FR-004**: The pipeline MUST follow three stages: extract (creates elements) → enrich (modifies elements in-place) → commit (finalizes to registry). Enrichment MUST NOT create new elements.
- **FR-005**: Enrichment MUST only modify non-hash fields: `ontology_annotations`, `value_domain`, `question_text`, and provenance entries. It MUST NOT modify any field in `_EXCLUDED_FROM_HASH`'s complement (the hashed fields).
- **FR-006**: After enrichment, the sha256 of every element MUST match its pre-enrichment sha256 (identity unchanged).

**In-Place Enrichment**

- **FR-007**: `enrich` command MUST update element files in-place — adding `ontology_annotations`, `value_domain`, and enrichment provenance to existing files. No new files created.
- **FR-008**: Enrichment provenance MUST be appended to the existing provenance list with `activity: enrichment`.
- **FR-009**: Re-running enrichment MUST be idempotent when ontology state hasn't changed.
- **FR-010**: The `_create_enriched_element()` function (which creates new elements with derived_from) MUST be removed or disabled. Enrichment uses `_update_element_in_place()` instead.

**Commit Stage**

- **FR-011**: The commit stage MUST rehash each enriched element from its final semantic content and write it to the registry under the content-addressed filename `{name}_{hash}.yaml`.
- **FR-012**: Staged elements MUST be stored in a temporary staging directory (e.g., `{output_dir}/.staging/{run_id}/`), separate from the registry. They carry a pipeline run ID.
- **FR-013**: After commit, staged elements MUST be deleted. Only the final content-addressed element in the registry persists.
- **FR-014**: If two staged elements produce the same final hash at commit time, they MUST be merged — provenance entries combined into a single registry file.
- **FR-015**: No provenance for intermediate pipeline stages. The committed element's provenance reflects the source extraction + enrichment attribution, not the staging mechanics.
- **FR-016**: If the pipeline is interrupted before commit, the staging directory MUST be cleaned up on the next run (stale staging dirs detected by run ID age).

**Curation Exception**

- **FR-017**: Manual curation (`activity: curation`) MAY create new elements with `derived_from` links in the future. This is explicitly out of scope for enrichment but the architecture MUST support it.

### Key Entities

- **Staged Element**: An element in the extract stage — has semantic identity + provenance but no enrichment metadata yet.
- **Enriched Element**: Same element with ontology_annotations, value_domain, and enrichment provenance added in-place. Same sha256 as staged.

## Success Criteria

### Measurable Outcomes

- **SC-001**: Element count after enrichment equals element count after extraction (zero new elements from enrichment).
- **SC-002**: sha256 of every element is identical before and after enrichment.
- **SC-003**: All enriched elements have ontology_annotations (where matches exist above threshold).
- **SC-004**: Full pipeline (extract 5 sources + enrich) produces ≤ 8,000 elements (not 14,000+ as currently).
- **SC-005**: Two elements differing only in ontology_term produce the same sha256.

### Assumptions

- ontology_term is moved from identity to metadata. This is a one-time migration for existing elements.
- response_options resolution (matching to ValueConcept URIs) updates the annotation metadata, not the semantic identity block's response_options field.
- The `derived_from` chain from enrichment is eliminated. Elements have a flat provenance list, not a derivation tree.
- Future curation features will re-introduce identity-changing operations with explicit user approval.
