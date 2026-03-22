# Identity Model Examples & Artifact Consistency Review

## Reproschema Concept Mapping

| reproschema | undata artifact | Properties | Notes |
|------------|----------------|------------|-------|
| Protocol | — | — | Not modeled (protocol = collection of activities) |
| Activity | SchemaRecord | properties (element URIs), subclass_of, mixins | Activity ≈ a form/assessment with ordered items |
| Item | ElementRecord | data_type, unit, response_options, question_text, min/max, ontology_annotations | Item ≈ a single question/variable |
| ResponseOption | ResponseOption (embedded in Element) | value, label, ontology_term | Choices for a categorical element |
| Choice | ValueConcept | label, value_type, ontology_annotations | A standalone semantic value entity |
| — | ValueSetRecord | name, members (ValueConcept URIs) | Named collection of choices (e.g., SexEnum) |

### Gaps identified

| Gap | Issue | Recommendation |
|-----|-------|----------------|
| **Element missing `description`** | reproschema Item has `description`. SemanticIdentity has `question_text` but no `description`. Description is only in ProvenanceEntry. | Add `description: str \| None` to SemanticIdentity (NOT in hash for ontology-anchored mode; IN hash for structural fallback) |
| **Element missing `preamble`/`instruction`** | reproschema Item can have administration instructions | Out of scope — not needed for data elements |
| **Schema missing `ontology_annotations`** | SchemaIdentity has no ontology_annotations field | Add `ontology_annotations: list[OntologyAnnotation] \| None` to SchemaIdentity |
| **Schema missing `description`** | SchemaIdentity has no description | Add via SchemaProvenance (already has `description`) — or add to SchemaIdentity for the canonical description |
| **ValueConcept missing `description`** | ValueSemanticIdentity has only label + value_type | Add `description: str \| None` for richer matching |
| **ValueProvenance too minimal** | Only `source` + `raw_value` — no PROV-O fields | Align with ProvenanceEntry (add generated_at, attributed_to, activity, source_ref) |
| **SchemaProvenance ≠ ProvenanceEntry** | Different models for element vs schema provenance | Unify: use ProvenanceEntry for all registry entities |
| **Constraints redundant** | `constraints.allowed_values` overlaps with `response_options`; `constraints.minimum/maximum` replaced by `min_value/max_value` | Remove Constraints entirely — it's legacy |

---

## Example 1: Age across sources (merge vs link)

### Staged (post-extraction, pre-enrichment)

```yaml
# Staged element A (BIDS) — UUID, no hash yet
_staging_id: "a1b2c3d4"
semantic:
  data_type: float
  unit: year
  value_domain: numeric
provenance:
  - source: bids
    class: participant
    name: age
    description: "Age of the participant in years"

# Staged element B (NWB) — different representation
_staging_id: "e5f6g7h8"
semantic:
  data_type: string
  unit: iso8601_duration
  value_domain: text
provenance:
  - source: nwb
    class: Subject
    name: age
    description: "Age of the subject"
```

### After enrichment

```yaml
# Element A enriched
_staging_id: "a1b2c3d4"
semantic:
  data_type: float
  unit: year
  value_domain: numeric
  ontology_annotations:
    - term_uri: http://purl.obolibrary.org/obo/NCIT_C25150
      term_label: Age
      ontology: ncit
      mapping_relation: skos:exactMatch
      match_level: concept_match  # concept only — float/year not in ontology
      score: 0.97
      model: all-MiniLM-L6-v2
      primary: true
provenance:
  - source: bids
    class: participant
    name: age
    description: "Age of the participant in years"
  - source: enrichment
    activity: enrichment
    attributed_to: urn:undata:enrichment-pipeline

# Element B enriched — SAME ontology URI, DIFFERENT data shape
_staging_id: "e5f6g7h8"
semantic:
  data_type: string
  unit: iso8601_duration
  value_domain: text
  ontology_annotations:
    - term_uri: http://purl.obolibrary.org/obo/NCIT_C25150
      term_label: Age
      ontology: ncit
      mapping_relation: skos:exactMatch
      match_level: concept_match
      score: 0.96
      model: all-MiniLM-L6-v2
      primary: true
provenance:
  - source: nwb
    class: Subject
    name: age
    description: "Age of the subject"
  - source: enrichment
    activity: enrichment
    attributed_to: urn:undata:enrichment-pipeline
```

### After commit (hashing)

Element A hash (ontology-anchored): `sha256(canonical({data_type: float, unit: year, primary_ontology_uri: NCIT_C25150}))` → `age_abc123def456.yaml`

Element B hash (ontology-anchored): `sha256(canonical({data_type: string, unit: iso8601_duration, primary_ontology_uri: NCIT_C25150}))` → `age_789012345678.yaml`

**Result**: Two separate elements (different data_type + unit) linked by a **type_conversion transform**. Same ontology concept, different representation.

---

## Example 2: Sex across sources (merge)

### Staged

```yaml
# BIDS sex
_staging_id: "s1"
semantic:
  data_type: string
  response_options:
    - {value: "male", label: "Male"}
    - {value: "female", label: "Female"}
    - {value: "other", label: "Other"}
provenance:
  - source: bids
    class: participant
    name: sex
    description: "Biological sex"

# DANDI sex — same response options, same data type
_staging_id: "s2"
semantic:
  data_type: string
  response_options:
    - {value: "female", label: "Female"}
    - {value: "male", label: "Male"}
    - {value: "other", label: "Other"}
provenance:
  - source: dandi
    class: BioSample
    name: sex
    description: "Sex of the subject"
```

### After enrichment + commit

Both get `primary_ontology_uri: PATO_0000047` (Sex). Hash is `sha256(canonical({data_type: string, response_options: [{value: female}, {value: male}, {value: other}], primary_ontology_uri: PATO_0000047}))` — **identical hash** (response_options sorted by value).

**Result**: **Merged** into one element with combined provenance:

```yaml
sha256: "..."
semantic:
  data_type: string
  response_options:
    - {value: "female", label: "Female"}
    - {value: "male", label: "Male"}
    - {value: "other", label: "Other"}
  value_domain: categorical
  ontology_annotations:
    - term_uri: http://purl.obolibrary.org/obo/PATO_0000047
      term_label: biological sex
      ontology: pato
      mapping_relation: skos:exactMatch
      match_level: concept_match
      score: 0.98
      model: all-MiniLM-L6-v2
      primary: true
provenance:
  - source: bids
    class: participant
    name: sex
    description: "Biological sex"
  - source: dandi
    class: BioSample
    name: sex
    description: "Sex of the subject"
  - source: enrichment
    activity: enrichment
    attributed_to: urn:undata:enrichment-pipeline
```

---

## Example 3: PHQ-9 items (same response options, different concepts)

### Staged

```yaml
# PHQ-9 item 1: "Little interest or pleasure in doing things"
_staging_id: "phq1"
semantic:
  data_type: integer
  min_value: 0
  max_value: 3
  response_options:
    - {value: "0", label: "Not at all"}
    - {value: "1", label: "Several days"}
    - {value: "2", label: "More than half the days"}
    - {value: "3", label: "Nearly every day"}
provenance:
  - source: redcap
    class: PHQ9
    name: phq9_interest
    description: "Little interest or pleasure in doing things"

# PHQ-9 item 2: "Feeling tired or having little energy"
_staging_id: "phq2"
semantic:
  data_type: integer
  min_value: 0
  max_value: 3
  response_options:
    - {value: "0", label: "Not at all"}
    - {value: "1", label: "Several days"}
    - {value: "2", label: "More than half the days"}
    - {value: "3", label: "Nearly every day"}
provenance:
  - source: redcap
    class: PHQ9
    name: phq9_fatigue
    description: "Feeling tired or having little energy"
```

### After enrichment

Item 1 maps to different ontology concept than Item 2 (different primary_ontology_uri).

If NO high-precision ontology match → **structural fallback**:
- Item 1 hash: `sha256({data_type: integer, min_value: 0, max_value: 3, response_options: [...], class: PHQ9, attribute: phq9_interest, description: "Little interest..."})`
- Item 2 hash: `sha256({data_type: integer, min_value: 0, max_value: 3, response_options: [...], class: PHQ9, attribute: phq9_fatigue, description: "Feeling tired..."})`

**Result**: Two separate elements despite identical response options — differentiated by `class + attribute + description` in fallback hash.

---

## Example 4: Device name with context

### Staged

```yaml
# Generic device name
_staging_id: "d1"
semantic:
  data_type: string
provenance:
  - source: nwb
    class: Device
    name: name
    description: "Name of the device"

# MRI-specific device name
_staging_id: "d2"
semantic:
  data_type: string
provenance:
  - source: aind
    class: MRIDevice
    name: name
    description: "Name of the MRI device"
```

### After enrichment + commit

If both get different ontology annotations (Device concept ≠ MRI Device concept) → **different hashes, separate elements**.

If neither gets a high-precision match → structural fallback:
- d1: `sha256({data_type: string, class: Device, attribute: name, description: "Name of the device"})`
- d2: `sha256({data_type: string, class: MRIDevice, attribute: name, description: "Name of the MRI device"})`

**Result**: Two separate elements — different class + description.

---

## Example 5: Value enrichment (element_match)

```yaml
# Value "male" — after enrichment
sha256: "..."
semantic:
  value_type: categorical
  label: male
  ontology_annotations:
    - term_uri: http://purl.obolibrary.org/obo/PATO_0000384
      term_label: male
      ontology: pato
      mapping_relation: skos:exactMatch
      match_level: element_match    # exact data value match
      score: 0.99
      model: all-MiniLM-L6-v2
      primary: true
provenance:
  - source: bids
    raw_value: "M"
  - source: dandi
    raw_value: "male"
```

---

## Artifact Consistency Issues

### 1. Provenance models are not unified

| Entity | Provenance Model | PROV-O fields? | source_ref? |
|--------|-----------------|----------------|-------------|
| Element | ProvenanceEntry | Yes (generated_at, attributed_to, activity, derived_from) | No |
| Schema | SchemaProvenance | Yes (added in 024) | Yes |
| Value | ValueProvenance | **No** (only source + raw_value) | **No** |
| ValueSet | ProvenanceEntry | Yes | No |

**Fix needed**: Unify all provenance to ProvenanceEntry (or a common base). ValueProvenance is too minimal.

### 2. ontology_annotations not on all entity types

| Entity | Has ontology_annotations? |
|--------|--------------------------|
| Element (SemanticIdentity) | Yes |
| Schema (SchemaIdentity) | **No** |
| Value (ValueSemanticIdentity) | Yes |
| ValueSet (ValueSetIdentity) | **No** |

**Fix needed**: Add to SchemaIdentity and ValueSetIdentity.

### 3. Constraints is legacy/redundant

`Constraints.allowed_values` duplicates `response_options`. `Constraints.minimum/maximum` is replaced by `min_value/max_value`. `Constraints.pattern` is the only unique field.

**Fix needed**: Remove Constraints; move `pattern` to SemanticIdentity directly.

### 4. description not consistently available for identity fallback

The fallback hash needs `description`, but it's stored differently per entity:
- Element: in ProvenanceEntry (varies per source — which one?)
- Schema: in SchemaProvenance
- Value: not available
- ValueSet: not available

**Fix needed**: Add canonical `description` to all semantic identity blocks (NOT in hash for ontology-anchored mode; IN hash for structural fallback only).
