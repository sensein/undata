# Quickstart: System Hardening

## 1. LLM Chat

```bash
# Ensure ollama is running with a model
ollama pull qwen3:0.6b
export OLLAMA_HOST=http://localhost:11434

# Or use OpenAI
export OPENAI_API_KEY=sk-...

# Open chat for an element
# Visit: http://localhost:3000/curation/chat?entity=<sha256>&type=element
# Type a message → LLM responds with entity-aware suggestions
```

## 2. Name-Based Transforms

```bash
# Run transform pipeline (now uses name + embedding similarity)
uv run undata-library transform /path/to/registry
# Expected: 100+ transforms (up from 15)
```

## 3. Additional Sources

```bash
# Ingest OpenNeuro dataset
uv run undata-library ingest --source openneuro --path ds000228

# Ingest ReproSchema library
uv run undata-library ingest --source reproschema --path /path/to/reproschema-library

# NDA data dictionary
uv run undata-library ingest --source nda --path ABCD_T1w
```

## 4. Search Modes

Visit http://localhost:3000/search
- Toggle: Lexical | Semantic | Both
- Lexical: exact keyword matches
- Semantic: embedding similarity (finds "brain_region" when searching "brain area")

## 5. Ontology Admin

Visit http://localhost:3000/admin/ontologies
- Shows loaded ontologies from pyoxigraph store
- Term counts, checksums, last refresh dates

## 6. Version Check

```bash
# Check for dependency updates
curl -s http://localhost:8002/graphql -H "Content-Type: application/json" \
  -d '{"query":"mutation { checkDependencyVersions { name hasUpdate } }"}'
```

## 7. Audit Log

```bash
# Query audit log for an entity
curl -s http://localhost:8002/graphql -H "Content-Type: application/json" \
  -d '{"query":"{ auditLog(entityRef: \"<sha256>\", first: 10) { activity agent createdAt } }"}'
```
