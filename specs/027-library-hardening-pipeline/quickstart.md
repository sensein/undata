# Quickstart: 027 Validation Scenarios

## QS-001: Library cleanup — no private imports across modules
```bash
# After US1 cleanup, verify no underscore imports cross module boundaries
grep -rn "from \.\w* import _" library/src/undata_library/ | grep -v "__init__" | grep -v "test"
# Expected: 0 matches
```

## QS-002: Shared utilities in use
```bash
# Verify safe_load_yaml utility exists and is used
grep -rn "safe_load_yaml" library/src/undata_library/
# Expected: defined in utils.py, imported in 5+ modules
```

## QS-003: Full pipeline re-extraction matches baseline
```bash
undata-library pipeline --source bids --output-dir /tmp/qs003
# Expected: elements >= 1036, enrichment rate >= 5.6%
```

## QS-004: Curation flags generated for borderline matches
```bash
undata-library pipeline --source bids --output-dir /tmp/qs004
ls /tmp/qs004/curation-flags/*.yaml | wc -l
# Expected: > 0 flags generated
```

## QS-005: LLM verification for borderline matches
```bash
undata-library pipeline --source bids --output-dir /tmp/qs005
grep "llm_verification" /tmp/qs005/curation-flags/*.yaml | head -3
# Expected: LLM verification results present with model, response, confidence
```

## QS-006: Run summary produced
```bash
undata-library pipeline --source bids --output-dir /tmp/qs006
cat /tmp/qs006/runs/*.yaml
# Expected: YAML with entity_counts, enrichment_rate, curation_flags, timing
```

## QS-007: Delta detection on re-extraction
```bash
# Run twice, second should show delta
undata-library pipeline --source bids --output-dir /tmp/qs007
undata-library pipeline --source bids --output-dir /tmp/qs007
# Expected: delta section shows 0 added, 0 removed (no changes)
```

## QS-008: New entity flows through full pipeline
```bash
# Add a synthetic element to staging, run enrich → commit → align
# Verify it appears in committed registry with content-addressed name
# Verify it's included in alignment and transform generation
```

## QS-009: GraphQL API serves elements
```bash
curl -X POST http://localhost:8000/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "{ browseElements(first: 5) { edges { node { sha256 semantic { dataType } } } } }"}'
# Expected: 200 OK with 5 elements
```

## QS-010: Curator can resolve flag via UI
```
1. Open curation queue in browser
2. Click a pending flag
3. Review evidence panel (candidates, scores, LLM justification)
4. Click "Approve" with a note
5. Verify flag status changes to "approved"
6. Verify element ontology_annotation is updated
```
