# Quickstart: Data Export, Import & Download Portal

## 1. Export Full Registry

```bash
# CLI export
uv run undata-library export-full --output /tmp/undata-export --version v2026.03.31

# Verify
ls /tmp/undata-export/
# Expected: manifest.json, elements/, schemas/, values/, valuesets/, transforms/,
#           curation-flags/, runs/, ontology-sources.yaml, embeddings.parquet

cat /tmp/undata-export/manifest.json | python3 -m json.tool
# Expected: version, timestamp, entity_counts, format_version
```

## 2. Round-Trip Test

```bash
# Export → clear → import → verify
uv run undata-library test-roundtrip --backend-url http://localhost:8002
# Expected: "Round-trip test PASSED: all entity counts match"
```

## 3. Import into Fresh Database

```bash
# Clear and import
docker compose down -v
docker compose up -d
# Wait for DB to be ready...
curl -X POST http://localhost:8002/graphql \
  -H "Content-Type: application/json" \
  -d '{"query": "mutation { importRegistry(registryPath: \"/tmp/undata-export\") { elements schemas values valuesets transforms flags runs } }"}'
```

## 4. Download Page

Visit http://localhost:3000/downloads
- See available nightly + versioned releases
- Click download → gets .tar.gz archive

## 5. Admin Import via UI

1. Log in as admin at http://localhost:3000
2. Go to Admin → Import
3. Upload a .tar.gz archive
4. Review entity counts preview
5. Click "Import" (optionally check "Clear existing data")
