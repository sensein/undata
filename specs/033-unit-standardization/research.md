# Research: Unit Standardization with QUDT

## R1: RDF Library Choice

**Decision**: Use pyoxigraph (already in library dependencies) to parse QUDT TTL. Build an in-memory lookup dict at load time.

**Rationale**: pyoxigraph is already a dependency for the ontology store. Adding rdflib would be a new heavy dep. The QUDT file is static reference data — parse once, cache as a dict keyed by symbol/label/ucumCode.

**Alternative**: rdflib (more SPARQL support but heavier, not needed for simple lookups).

## R2: QUDT Vocabulary Structure

**Finding**: 2,897 unit definitions with:
- `qudt:symbol` — primary lookup key ("kg", "m", "V")
- `qudt:ucumCode` — UCUM standard code ("kg", "m", "V")
- `rdfs:label` — human-readable names ("Kilogram"@en)
- `qudt:conversionMultiplier` + `qudt:conversionOffset` — conversion to base unit
- `qudt:hasQuantityKind` — physical dimension (Mass, Length, etc.)
- `qudt:hasDimensionVector` — dimensional analysis vector

**Decision**: Build a resolver that indexes by: lowercase symbol, lowercase ucumCode, lowercase label (all three as lookup keys pointing to the same QUDT URI). This handles "kg" = "KG" = "kilogram" = "Kilogram" automatically.

## R3: Unit Alias Table

**Decision**: In addition to QUDT-derived aliases, maintain a small hand-curated alias table for common neuroscience unit variants not in QUDT:
- "years" → qudt:YR
- "yr" → qudt:YR
- "months" → qudt:MO
- "days" → qudt:DAY
- "seconds" → qudt:SEC
- "milliseconds" → qudt:MilliSEC
- "microvolt" → qudt:MicroV
- "millimeter" → qudt:MilliM

**Rationale**: QUDT uses specific symbols (YR, MO, DAY) but source schemas often use natural language ("years", "months"). A small alias table bridges this gap.

## R4: QUDT File Location

**Decision**: Copy QUDT TTL to `library/src/undata_library/data/qudt/VOCAB_QUDT-UNITS-ALL.ttl` so the library is self-contained. The backend's copy becomes redundant.

**Rationale**: The library should not depend on files in the backend directory. Bundling the TTL in the library package makes it available to both CLI and backend users.

## R5: Integration Point in Pipeline

**Decision**: Unit resolution runs as part of the enrichment stage, after extraction and before alignment. New function `resolve_units()` in a `unit_resolver.py` module. Called by `enrich_all()` as the first step.

**Rationale**: Enrichment already modifies entities in-place. Unit resolution is conceptually the same — enriching the `unit` field with canonical data. Running before alignment ensures normalized units are available for cross-source matching.

## R6: Hash Impact

**Decision**: When computing the identity hash, use `unit_uri` (QUDT URI) if available, otherwise fall back to raw `unit` string. This means the hash uses `http://qudt.org/vocab/unit/KiloGM` instead of "kg" — making "kg" and "kilogram" hash identically.

**Rationale**: The hash must be deterministic and canonical. QUDT URIs are the canonical form. Fallback to raw string preserves behavior for units not in QUDT.
