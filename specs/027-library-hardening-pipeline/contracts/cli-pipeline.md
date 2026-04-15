# CLI Pipeline Contract

## Updated Pipeline Command

```bash
# Full pipeline with run summary + curation flags
undata-library pipeline --source bids --output-dir /path/to/registry

# Output includes:
# [1/5] Extracting bids to staging...
# [2/5] Enriching all entity types...
#   LLM verification: 23 borderline matches evaluated
# [3/5] Committing to registry...
# [4/5] Aligning elements...
# [5/5] Generating transforms...
#
# Run Summary (saved to /path/to/registry/runs/2026-03-22T12:00:00.yaml):
#   Elements: 1,036 (58 enriched, 12 flagged)
#   Values: 295 (90 enriched, 5 flagged)
#   Schemas: 12 (8 enriched, 0 flagged)
#   Transforms: 148 (52 needs-review)
#   Delta from previous: +3 elements, -1 schema, +12 transforms
```

## Curation Flag Output

```bash
# View curation queue
undata-library curation-queue --status pending
# Output: YAML list of CurationFlag objects

# Resolve a flag
undata-library resolve-flag --id <flag-id> --action approve --note "Confirmed match"
```

## Run Summary Output Format

```yaml
run_id: "2026-03-22T12:00:00-bids"
source: bids
started_at: "2026-03-22T12:00:00Z"
completed_at: "2026-03-22T12:02:30Z"
entity_counts:
  extract: {elements: 1036, schemas: 12, values: 295, valuesets: 7}
  enrich: {elements: 58, values: 90, schemas: 8, valuesets: 0}
  commit: {committed: 1350, merged: 0}
  align: {pairs: 1822, groups: 1}
  transform: {created: 148}
curation_flags:
  low_confidence: 8
  ambiguous_match: 4
  unknown_transform: 52
  total: 64
delta:
  elements: {added: 3, removed: 0, modified: 2}
  schemas: {added: 0, removed: 1, modified: 0}
timing:
  extract_s: 3.1
  enrich_s: 32.7
  commit_s: 2.2
  align_s: 5.0
  transform_s: 1.5
  total_s: 44.5
```
