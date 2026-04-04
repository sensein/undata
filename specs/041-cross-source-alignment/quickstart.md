# Quickstart: Cross-Source Alignment

## Scenario 1: Run alignment on full pipeline output

```bash
# Run full pipeline for all sources
cd library
uv run undata-library pipeline --source bids
uv run undata-library pipeline --source nwb
uv run undata-library pipeline --source dandi
uv run undata-library pipeline --source openminds
uv run undata-library pipeline --source aind
uv run undata-library pipeline --source reproschema
uv run undata-library pipeline --source nda
uv run undata-library pipeline --source openneuro

# Run alignment across all sources
uv run undata-library align --threshold 0.7

# Check alignment report
cat ~/.cache/undata/registry/alignment-report.yaml
```

**Expected**: Element count drops by 50%+. Known cross-source pairs (age↔interview_age) aligned.

## Scenario 2: Verify SchemaView dedup for OpenNeuro

```bash
# Run OpenNeuro extraction only
uv run undata-library pipeline --source openneuro --stage extract

# Check entity count before alignment
uv run undata-library inspect --source openneuro --count

# Expected: participant_id, age, sex each appear ONCE (not 100x)
# because SchemaView unified slots across dataset classes
```

## Scenario 3: Search-driven feedback loop

```bash
# Start backend + frontend
docker compose up -d

# Search for "age" in semantic mode
# → Should return 1 canonical element with provenance from BIDS + NDA + OpenNeuro
# → If it returns 2+ unaligned elements, they should be flagged as candidates
```

## Scenario 4: Verify alignment in UI

```
1. Browse to http://localhost:3000/elements
2. Click any element that has multiple sources in provenance
3. Verify "Aligned From" section shows contributing source elements
4. Verify alignment confidence scores are displayed
```

## Scenario 5: Adapter LinkML verification

```bash
# For each adapter, verify SchemaDefinition production
cd library
uv run python -c "
from undata_library.adapters.reproschema import ReproSchemaAdapter
a = ReproSchemaAdapter('/path/to/reproschema-library')
sd = a.to_linkml()
print(f'Classes: {len(sd.classes)}, Slots: {len(sd.slots)}, Enums: {len(sd.enums)}')
"
```

**Expected**: All 8 adapters produce valid SchemaDefinitions with >0 classes and slots.
