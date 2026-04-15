# Quickstart: 031 CivicDB UI Validation

## QS-001: Element grid is sortable
```
Open /elements → click "Type" column header → elements sort by type
Click again → reverse sort order
```

## QS-002: Clickable counts navigate
```
Open /elements → see an element with ontology annotation
Click the annotation badge → navigates to annotation detail or expands
```

## QS-003: Consistent detail page layout
```
Click any element → detail shows: identity block → description →
semantic properties → provenance → annotations → related schemas
```

## QS-004: Bidirectional navigation works
```
Element detail → "Used in schemas" → click schema → schema detail →
properties list → click an element → back to an element detail
```

## QS-005: Source color badges consistent
```
Browse elements → BIDS elements have blue badges, DANDI green,
NWB purple, openMINDS orange, AIND teal
```

## QS-006: Curation evidence panel
```
Open /curation → click a flag → evidence panel shows match candidates
with similarity scores
```

## QS-007: Mobile responsive
```
Resize browser to 375px → tables become cards, nav collapses
```

## QS-008: Playwright tests pass
```
pnpm exec playwright test — all tests pass including navigation traversal
```
