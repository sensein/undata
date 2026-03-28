# Contract: LLM Tool Definitions

## Tools Available to the Curation LLM

### propose_entity_change

```json
{
  "name": "propose_entity_change",
  "description": "Propose a change to an entity field. Validates against schema. Returns diff preview.",
  "parameters": {
    "entity_type": "elements | schemas | values | valuesets",
    "sha256": "string (entity identifier)",
    "field": "string (field path, e.g. 'unit', 'semantic.data_type', 'ontology_annotations')",
    "value": "any (new value for the field)"
  },
  "returns": { "success": "bool", "diff": "{ field, old_value, new_value }", "validation_error": "string | null" }
}
```

### create_entity

```json
{
  "name": "create_entity",
  "description": "Propose creation of a new entity. Validates all required fields. Returns preview.",
  "parameters": {
    "entity_type": "elements | schemas | values | valuesets",
    "data": "object (entity fields: semantic, provenance)"
  },
  "returns": { "success": "bool", "preview": "object (full entity)", "validation_error": "string | null" }
}
```

### delete_entity

```json
{
  "name": "delete_entity",
  "description": "Propose deletion of an entity. Records reason.",
  "parameters": {
    "entity_type": "elements | schemas | values | valuesets",
    "sha256": "string",
    "reason": "string"
  },
  "returns": { "success": "bool", "entity_summary": "string" }
}
```

### lookup_ontology_term

```json
{
  "name": "lookup_ontology_term",
  "description": "Search the ontology store for a term. Returns validated URIs. Use this instead of guessing URIs.",
  "parameters": {
    "query": "string (search text)",
    "ontology": "string | null (optional: restrict to specific ontology like 'ncit', 'uberon')",
    "limit": "integer (default 5)"
  },
  "returns": { "results": [{ "uri": "string", "label": "string", "ontology": "string", "synonyms": ["string"] }] }
}
```

### fetch_entity

```json
{
  "name": "fetch_entity",
  "description": "Load an entity's full details for context.",
  "parameters": {
    "entity_type": "elements | schemas | values | valuesets",
    "sha256": "string"
  },
  "returns": "object (full entity with semantic, provenance, ontology_annotations)"
}
```

### trigger_ingestion

```json
{
  "name": "trigger_ingestion",
  "description": "Trigger pipeline ingestion for a source. Results are staged for review.",
  "parameters": {
    "source_url": "string (repository URL or path)",
    "adapter_pattern": "string (adapter name: bids, nwb, dandi, openminds, aind, json-schema, linkml)"
  },
  "returns": { "success": "bool", "stats": "{ elements, schemas, values, valuesets }", "staged_entities": "integer" }
}
```

## System Prompt Template

The LLM system prompt includes:
- Current entity context (if reviewing a specific entity)
- Available tools list with descriptions
- Instructions: "You are a curation assistant for the undata data element registry. Help curators review, edit, and improve entity metadata. Always use lookup_ontology_term to validate ontology URIs — never guess. Propose changes via propose_entity_change — never output raw JSON for the user to copy."
