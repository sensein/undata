# Quickstart: 030 Frontend Integration Validation

## QS-001: Element browser loads with seed data
```bash
cd backend && docker compose up -d
cd frontend && pnpm dev
# Open http://localhost:3000/elements
# Expected: 5 elements displayed with name, source, data type
```

## QS-002: Element detail page renders
```bash
# Click any element in the browser
# Expected: detail page shows semantic properties, provenance, annotations
```

## QS-003: Filter by source works
```bash
# Select "bids" from source dropdown
# Expected: only BIDS elements shown
```

## QS-004: Pagination works
```bash
# With >20 elements imported, scroll or click "Load more"
# Expected: additional elements load
```

## QS-005: Schema browser loads
```bash
# Navigate to /schemas
# Expected: schemas displayed with properties list
```

## QS-006: Value browser loads
```bash
# Navigate to /values
# Expected: values displayed with labels and annotations
```

## QS-007: Error state when backend down
```bash
docker compose down
# Refresh /elements
# Expected: error message shown, not blank page
```

## QS-008: Playwright tests pass
```bash
cd backend && docker compose up -d
cd frontend && pnpm exec playwright test
# Expected: all tests pass
```
