# Data Model: undata-library v2

## Element (Property) — `elements/{attribute}_{6-char-id}.yaml`

```yaml
semantic:                          # IDENTITY — hashed for content-addressed URI
  ontology_term: uriorcurie | null # Ontology concept (e.g., NCIT:C124353)
  data_type: DataType              # string | integer | float | boolean | array | object
  unit: string | null              # Measurement unit (UCUM/QUDT symbol)
  constraints:                     # Validation constraints (optional)
    minimum: number | null
    maximum: number | null
    pattern: string | null
    allowed_values: list[string] | null

provenance:                        # PROVENANCE — NOT part of identity hash
  - source: string                 # Source system (bids, nwb, dandi, aind, openminds)
    class: string                  # Defining class in source (Participant, Subject, Device)
    name: string                   # Attribute name in source (age, subject_age)
    description: string | null     # Source description
    required: boolean | null       # Required in this source context
    multivalued: boolean | null    # Multivalued in this source context
```

### Identity Hash Function

```
input = canonical_json({ontology_term, data_type, unit, constraints})
       → sorted keys, nulls omitted, compact JSON
hash  = sha256(input)
key   = base36_encode(hash[:4])[:6]   # 6-char alphanumeric
uri   = https://schema.undata.live/elements/{name}_{key}
file  = elements/{name}_{key}.yaml
```

Where `name` is the most common attribute name across provenance entries.

## Schema (Class Shape) — `schemas/{name}_{6-char-id}.yaml`

```yaml
semantic:                          # IDENTITY — hashed
  properties:                      # Ordered list of element URIs
    - https://schema.undata.live/elements/age_x7k2m9
    - https://schema.undata.live/elements/sex_y8l3n0
  subclass_of: uriorcurie | null   # Parent schema URI
  mixins:                          # Mixin schema URIs
    - uriorcurie

provenance:                        # NOT part of identity hash
  - source: string
    name: string                   # Class name in source
    description: string | null
```

### Schema Identity Hash

```
input = canonical_json({properties: [sorted URIs], subclass_of, mixins: [sorted URIs]})
hash  = sha256(input)
key   = base36_encode(hash[:4])[:6]
```

## Mapping — `mappings/{6-char-id}.yaml`

```yaml
source_element: uriorcurie         # Input property URI
target_element: uriorcurie         # Output property URI
function_type: MappingFunctionType # identity | unit_conversion | scaling | structural
expression: string | null          # Transformation expression
expression_type: string | null     # python | jexl | unit_factor
confidence: float | null           # 0.0–1.0
sssom_predicate: string | null     # skos:exactMatch, skos:closeMatch, etc.

provenance:
  - source: string
    attributed_to: uriorcurie | null
```

Note: identity mappings between elements with the SAME content hash are unnecessary
(they're the same element). Mappings only exist between DIFFERENT elements.

## Hash Registry — `hash-registry.yaml`

```yaml
elements:
  x7k2m9:
    sha256: a1b2c3d4e5f6...
    attribute: age
    uri: https://schema.undata.live/elements/age_x7k2m9
  y8l3n0:
    sha256: f6e5d4c3b2a1...
    attribute: sex
    uri: https://schema.undata.live/elements/sex_y8l3n0

schemas:
  a1b2c3:
    sha256: 1234567890ab...
    name: participant
    uri: https://schema.undata.live/schemas/participant_a1b2c3
```

## Enums

```
DataType:        string | integer | float | boolean | array | object
MappingFunctionType: identity | unit_conversion | scaling | structural | unknown
```

## Relationships (RDF triples, implicit from file structure)

| Subject | Predicate | Object |
|---------|-----------|--------|
| Schema | `sh:property` | Element URI |
| Schema | `rdfs:subClassOf` | Parent Schema URI |
| Schema | `undata:mixin` | Mixin Schema URI |
| Element | `owl:equivalentProperty` | (automatic: same hash = same element) |
| Mapping | `sssom:subject_id` | Source Element URI |
| Mapping | `sssom:object_id` | Target Element URI |
