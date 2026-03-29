# Quickstart: UX & UI Overhaul

## Verify Search

```bash
# After docker compose up, test global search
curl -s http://localhost:8002/graphql -H "Content-Type: application/json" -d '{
  "query": "{ globalSearch(query: \"age\", limit: 5) { totalCount results { entityType name matchType score } } }"
}' | python3 -m json.tool

# Expected: elements named "age" (lexical) + related elements like "date_of_birth" (semantic)
```

## Verify Link Health

```bash
# Check status page
curl -s http://localhost:8002/graphql -H "Content-Type: application/json" -d '{
  "query": "{ linkHealthStatus { totalDomains healthyDomains unhealthyDomains lastCheckAt } }"
}' | python3 -m json.tool
```

## Visual Checks

1. **Element browse** (http://localhost:3000/elements): 20+ rows visible, unit column present, case-insensitive sorting on Name
2. **Schema detail** (click any schema): properties show EntityTag chips with popovers, not plain text
3. **Valueset detail** (click any valueset): members show value EntityTag chips
4. **Search**: type in global search bar → results grouped by type with match indicators
5. **Chat**: click "Chat about this" on any entity tag → chat opens with full context
6. **Assistant**: click "Assistant" in sidebar → chat opens without entity, can search within conversation
7. **Status**: http://localhost:3000/status → domain health dashboard
8. **Transforms**: http://localhost:3000/transforms → no array→singleton transforms without structural annotation
