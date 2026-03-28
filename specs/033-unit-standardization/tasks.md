# Tasks: Unit Standardization with QUDT

**Input**: Design documents from `/specs/033-unit-standardization/`
**Prerequisites**: plan.md, spec.md (with clarifications), research.md, quickstart.md

**Tests**: Included — TDD for unit resolver, regression for existing tests.

**Organization**: 5 user stories. US1 (QUDT resolution) + US2 (hash normalization) are tightly coupled P1s. US3 (adapter extraction) is independent P1. US4 (transforms) + US5 (cmixf) are P2s.

**Clarifications incorporated**:
- QUDT loads into OntologyStore alongside NCIT/PATO
- LLM extracts units from descriptions when unit field empty
- Multi-unit fields → one element per variant with transforms
- Paired value+unit fields → recognized, transforms generated
- String-encoded units → curation flag for decomposition

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel
- **[Story]**: Which user story (US1–US5)
- All paths relative to `library/src/undata_library/` unless noted

## Phase 1: Setup

**Purpose**: QUDT data, dependencies, model updates

- [X] T001 Copy QUDT TTL from `backend/data/qudt/VOCAB_QUDT-UNITS-ALL.ttl` to `library/src/undata_library/data/qudt/VOCAB_QUDT-UNITS-ALL.ttl` — bundle in library package
- [X] T002 Add QUDT to `source_defs/ontologies.yaml` — new entry with name "qudt", path to bundled TTL, format "ttl"
- [X] T003 Re-add `cmixf>=0.2` to `library/pyproject.toml` dependencies
- [X] T004 Add `unit_uri: str | None = None` field to `SemanticIdentity` in `models.py` — nullable, not included in hash exclusions
- [X] T005 Add `unresolved_unit` and `unit_encoded_string` to `FlagType` enum in `models.py`

**Checkpoint**: Data bundled, model updated, deps ready

---

## Phase 2: Foundational — QUDT in OntologyStore + UnitResolver

**Purpose**: Core resolution service — BLOCKS enrichment integration

**⚠️ CRITICAL**: All unit enrichment depends on the resolver

### Tests

- [X] T006 Write `library/tests/test_unit_resolver.py` — tests: load QUDT vocab (≥2800 units), resolve "kg" → qudt:KiloGM, resolve "kilogram" → same URI, resolve "years" → qudt:YR, resolve "yr" → same URI as "years", resolve "wobbles" → None, resolve None → None, conversion_factor(YR, MO) → 12.0, alias table works

### Implementation

- [X] T007 [US1] Update `ontology_store.py` — add `load_qudt(path)` method that loads QUDT TTL into the pyoxigraph store. Add unit-specific query methods: `lookup_unit(symbol) → {uri, label, symbol, dimension}`, `search_units(query) → list` using qudt:symbol, qudt:ucumCode, rdfs:label as search fields
- [X] T008 [US1] Create `unit_resolver.py` — thin wrapper over OntologyStore:
  - `UNIT_ALIASES` dict mapping common neuroscience variants: years→YR, yr→YR, months→MO, days→DAY, seconds→SEC, milliseconds→MilliSEC, ms→MilliSEC, microvolt→MicroV, uV→MicroV, millivolt→MilliV, mV→MilliV, kilogram→KiloGM, gram→GM, meter→M, centimeter→CentiM, mm→MilliM, Hz→HZ, kHz→KiloHZ
  - `resolve(raw_string) → UnitResult | None` — try: alias table → OntologyStore symbol lookup → OntologyStore label lookup → None
  - `UnitResult` dataclass: uri, label, symbol, dimension, conversion_multiplier, conversion_offset
  - `conversion_factor(uri_a, uri_b) → float | None` — compute from QUDT conversionMultiplier values
- [X] T009 [US1] Run unit resolver tests — all must pass

**Checkpoint**: UnitResolver works with ≥50 common units. OntologyStore has QUDT loaded.

---

## Phase 3: User Story 2 — Hash Normalization (Priority: P1)

**Goal**: Equivalent units produce identical content hashes.

**Independent Test**: `age(unit="years")` and `age(unit="yr")` → same hash.

- [X] T010 [US2] Write hash normalization tests in `library/tests/test_unit_resolver.py` — two elements differing only in unit spelling ("kg" vs "kilogram") produce same canonical_json and same sha256 after enrichment
- [X] T011 [US2] Update `hashing.py` — in `canonical_json()`, when computing hash input, use `semantic.get("unit_uri", semantic.get("unit"))` so QUDT URI takes priority over raw string. Fallback to raw string when unit_uri absent
- [X] T012 [US2] Update `enrich.py` — add `resolve_units()` function called by `enrich_all()` as first step. For each entity with a `unit` field, call `UnitResolver.resolve(unit)` and set `unit_uri` in semantic block. Generate `unresolved_unit` curation flag for failures
- [X] T013 [US2] Add LLM unit extraction to `resolve_units()` — when `unit` is None/empty but `description` mentions a unit, call LLM with prompt: "Extract the unit of measurement from this description: '{description}'. Return only the unit symbol or 'none'." Resolve extracted symbol via QUDT
- [X] T014 [US2] Run full test suite — verify all 400+ existing tests pass plus new hash normalization tests

**Checkpoint**: Unit normalization works. Hash uses unit_uri. LLM extracts from descriptions.

---

## Phase 4: User Story 3 — Adapter Unit Extraction (Priority: P1)

**Goal**: All 5 adapters extract units from source schemas.

**Independent Test**: NWB extraction → elements with units populated.

- [ ] T015 [P] [US3] Update NWB adapter in `adapters/nwb.py` — extract unit from `dtype` field annotations, `quantity` attributes, and namespace-level unit declarations. Map to LinkML slot `unit` annotation
- [ ] T016 [P] [US3] Update DANDI adapter in `adapters/dandi.py` — extract unit from Pydantic model field metadata (`json_schema_extra`, `description` patterns)
- [ ] T017 [P] [US3] Update openMINDS adapter in `adapters/openminds.py` — extract unit from property `unitOfMeasurement` or linked `QuantitativeValue` patterns
- [ ] T018 [P] [US3] Update AIND adapter in `adapters/aind.py` — extract unit from JSON Schema `unit` or `units` properties in field definitions
- [ ] T019 [US3] Update standard extractor in `adapters/extractor.py` — when extracting slots from LinkML, preserve `unit` annotation and map to SemanticIdentity.unit
- [ ] T020 [US3] Detect multi-unit fields in adapters — when a field has `allowed_units: [...]` or similar, create one ClassifiedEntity per unit variant. Each variant has a single unit and distinct provenance noting the variant
- [ ] T021 [US3] Detect paired value+unit fields in adapters — when schema has `{name}` (numeric) + `{name}_unit` (enum), recognize the pair. Create unit-specific element variants for each enum value. Generate transforms: `{name}_in_{unit} = T({name}, {name}_unit)`
- [ ] T022 [US3] Detect string-encoded unit patterns — when a string field's description or response_options suggest embedded units (e.g., "120 mmHg"), generate `unit_encoded_string` curation flag
- [ ] T023 [US3] Run extraction for all 5 sources, count elements with `unit` populated — compare to brainstorm v1 baseline

**Checkpoint**: All adapters extract units. Multi-unit and paired fields handled.

---

## Phase 5: User Stories 4+5 — QUDT Transforms + cmixf (Priority: P2)

**Goal**: Replace hardcoded conversion table with QUDT factors. cmixf validation available.

**Independent Test**: Transform between year/month elements uses QUDT factor 12.0.

- [ ] T024 [US4] Update `transform.py` — replace `_UNIT_CONVERSIONS` hardcoded dict with QUDT-based lookup. For each element pair sharing an ontology term but differing in unit_uri, compute conversion factor via `UnitResolver.conversion_factor(uri_a, uri_b)`. Fall back to hardcoded table if QUDT unavailable
- [ ] T025 [US4] Handle paired-field transforms in `transform.py` — for recognized `(value, value_unit)` pairs, generate parametric transforms: `value_in_{unit} = value * factor` where factor comes from QUDT
- [ ] T026 [P] [US5] Add cmixf validation to `unit_resolver.py` — `validate_cmixf(unit_string) → {valid: bool, error: str | None}` using cmixf library. Called optionally during enrichment
- [ ] T027 [US4] Run transform generation, compare to brainstorm v1 — verify ≥20 QUDT-based conversion pairs (was 8 hardcoded)
- [ ] T028 [US5] Run cmixf validation on all extracted units — report valid/invalid counts

**Checkpoint**: QUDT-based transforms working. cmixf validation available.

---

## Phase 6: Polish + Validation

**Purpose**: Full regression, eval record, cleanup

- [ ] T029 Run full library test suite — all 400+ tests pass (`uv run pytest tests/ -v`)
- [ ] T030 Run full pipeline for BIDS source — verify unit_uri populated on elements, count unit resolution rate
- [ ] T031 Record unit resolution stats in `eval-record.md` — resolved count, unresolved count, LLM-extracted count, conversion pairs generated
- [ ] T032 Verify `ruff check` and `ruff format` pass on all modified files
- [ ] T033 Run quickstart validation QS-001 through QS-007
- [ ] T034 Push branch and verify CI is green

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies
- **Phase 2 (Resolver)**: Depends on Phase 1 — BLOCKS all unit work
- **Phase 3 (Hash Normalization)**: Depends on Phase 2
- **Phase 4 (Adapter Extraction)**: Depends on Phase 2 — can parallel with Phase 3
- **Phase 5 (Transforms + cmixf)**: Depends on Phase 3 + Phase 4
- **Phase 6 (Polish)**: Depends on all

### Parallel Opportunities

**Phase 4**: T015-T018 — all 4 adapter updates are independent files
**Phase 5**: T026 (cmixf) parallel with T024-T025 (transforms)

---

## Implementation Strategy

### MVP (Phases 1-3)

1. QUDT in OntologyStore + UnitResolver with alias table
2. Hash normalization using unit_uri
3. LLM extraction from descriptions
4. **STOP and VALIDATE**: "kg" and "kilogram" produce same hash

### Full Delivery

5. All adapters extract units + multi-unit/paired field handling
6. QUDT-based transforms + cmixf validation
7. Full regression + eval record + CI green

---

## Notes

- QUDT TTL is ~3MB, 2,897 units — loads in <3s via pyoxigraph
- Alias table covers the ~20 most common neuroscience unit variants
- LLM extraction uses existing litellm/ollama infrastructure — no new deps
- Multi-unit split follows the anyOf pattern from VISION.md (separate elements per variant)
- Paired-field detection is heuristic: `{name}` + `{name}_unit` naming convention
- Commit after each phase
