# Quickstart: Schema Explorer Frontend
**Feature**: 003-schema-explorer | **Date**: 2026-03-07

## Prerequisites

- 002-schema-backend running with data ingested (at least 10 elements)
- Node.js 20+ and `pnpm` installed

---

## 1. Install and run dev server

```bash
cd frontend
pnpm install
pnpm dev
# Opens at http://localhost:5173
```

---

## 2. Configure backend URL

```bash
# frontend/.env
PUBLIC_BACKEND_URL=http://localhost:8002/api/v1
PUBLIC_MIGRATION_URL=http://localhost:8004/api/v1
```

---

## 3. Verify search

1. Open `http://localhost:5173`
2. Type "age" in the search bar
3. Confirm results appear within 2 seconds with name, type, source badge
4. Click a result — confirm detail page opens at `/elements/{id}`

---

## 4. Verify relationship graph

1. Navigate to an element that has mappings (check `mapping_count > 0` in search results)
2. Confirm the relationship graph renders connected nodes
3. Click a connected node — confirm navigation to that element's detail page
4. Use depth slider to expand to depth 3 — confirm more nodes appear

---

## 5. Verify add element form

1. Navigate to `/add`
2. Submit with empty name — confirm validation error shown, no API call
3. Fill all required fields and submit — confirm redirect to new element's detail page
4. Search for the new element — confirm it appears immediately

---

## 6. Verify comparison view

1. From search results, select two elements (use checkbox or "compare" button)
2. Navigate to `/compare?a={id1}&b={id2}`
3. Confirm both elements' metadata shown side-by-side
4. Fields with same value: visually matched (e.g., green checkmark or no highlight)
5. Fields with different values: highlighted
6. If same data_type: "Register as Alias" button enabled; click and confirm success

---

## 7. Run tests

```bash
# Unit tests
pnpm test

# E2E tests (requires backend + dev server running)
pnpm exec playwright test
```

---

## Validation Checklist

- [ ] Dev server starts without errors
- [ ] Keyword search returns results within 2 seconds
- [ ] Filter by source reduces result set correctly
- [ ] Element detail page renders all metadata fields
- [ ] Relationship graph renders for elements with mappings
- [ ] Graph node click navigates to correct element detail page
- [ ] Depth slider changes graph depth without full page reload
- [ ] Search URL (`?q=age&source=BIDS`) is shareable — reload produces same results
- [ ] Add element form prevents submission with missing required fields
- [ ] New element appears in search within 5 seconds of creation
- [ ] Comparison view highlights differences and matches correctly
- [ ] "Register as Alias" creates an alias group in the backend
- [ ] Backend unavailable: explorer shows error message, not blank/stale data
