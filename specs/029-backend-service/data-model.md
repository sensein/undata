# Data Model: Backend Service

## Database Tables

All tables use UUID primary keys with `server_default` timestamps.

### Core Entity Tables

Each entity table stores the full entity as JSONB columns matching FileBackend's YAML structure.

```
elements
  id:                   UUID (PK, default uuid4)
  sha256:               VARCHAR (unique, indexed)
  file_name:            VARCHAR
  data_type:            VARCHAR (indexed)
  unit:                 VARCHAR
  pattern:              VARCHAR
  value_domain:         VARCHAR
  description:          TEXT
  min_value:            FLOAT
  max_value:            FLOAT
  type_ref:             VARCHAR
  semantic:             JSONB (full semantic block)
  provenance:           JSONB (array of provenance entries)
  ontology_annotations: JSONB (array of annotation objects)
  created_at:           TIMESTAMP (server_default now())

schemas
  id:                   UUID (PK)
  sha256:               VARCHAR (unique, indexed)
  file_name:            VARCHAR
  subclass_of:          VARCHAR
  is_mixin:             BOOLEAN
  properties:           JSONB (array of property URIs)
  description:          TEXT
  semantic:             JSONB
  provenance:           JSONB
  ontology_annotations: JSONB
  created_at:           TIMESTAMP

values
  id:                   UUID (PK)
  sha256:               VARCHAR (unique, indexed)
  file_name:            VARCHAR
  label:                VARCHAR (indexed)
  value_type:           VARCHAR
  ontology_id:          VARCHAR
  description:          TEXT
  semantic:             JSONB
  provenance:           JSONB
  ontology_annotations: JSONB
  created_at:           TIMESTAMP

valuesets
  id:                   UUID (PK)
  sha256:               VARCHAR (unique, indexed)
  file_name:            VARCHAR
  name:                 VARCHAR
  members:              JSONB (array of value URIs)
  description:          TEXT
  semantic:             JSONB
  provenance:           JSONB
  ontology_annotations: JSONB
  created_at:           TIMESTAMP
```

### Supporting Tables

```
curation_flags
  id:                   UUID (PK)
  entity_type:          VARCHAR
  entity_ref:           VARCHAR
  flag_type:            VARCHAR (indexed)
  context:              JSONB
  llm_verification:     JSONB (nullable)
  status:               VARCHAR (indexed, default 'pending')
  created_at:           TIMESTAMP
  resolved_at:          TIMESTAMP (nullable)
  resolved_by:          VARCHAR (nullable)
  resolution_note:      TEXT (nullable)

contributions
  id:                   UUID (PK)
  entity_type:          VARCHAR
  entity_ref:           VARCHAR
  contribution_type:    VARCHAR
  content:              JSONB
  status:               VARCHAR (default 'pending')
  contributor:          VARCHAR
  reviewed_by:          VARCHAR (nullable)
  reviewed_at:          TIMESTAMP (nullable)
  review_note:          TEXT (nullable)
  created_at:           TIMESTAMP

run_summaries
  id:                   UUID (PK)
  run_id:               VARCHAR
  source:               VARCHAR (indexed)
  started_at:           VARCHAR
  completed_at:         VARCHAR (nullable)
  entity_counts:        JSONB
  enrichment_rate:      JSONB (nullable)
  curation_flags:       JSONB (nullable)
  delta:                JSONB (nullable)
  timing:               JSONB (nullable)

user_profiles
  id:                   UUID (PK)
  external_sub:         VARCHAR (unique)
  email:                VARCHAR
  display_name:         VARCHAR
  role:                 VARCHAR (default 'viewer')
  created_at:           TIMESTAMP
```

## DatabaseBackend ↔ Table Mapping

| Protocol Method | SQL Operation |
|----------------|---------------|
| entities.read(type, id) | SELECT FROM {type} WHERE sha256 LIKE '{id}%' OR file_name = '{id}' |
| entities.write(type, data) | INSERT INTO {type} (...) ON CONFLICT (sha256) DO UPDATE |
| entities.list(type, **filters) | SELECT FROM {type} WHERE [filters on provenance JSONB, annotations, data_type] |
| entities.exists(type, id) | SELECT 1 FROM {type} WHERE sha256 LIKE '{id}%' LIMIT 1 |
| entities.delete(type, id) | DELETE FROM {type} WHERE sha256 LIKE '{id}%' |
| entities.merge_provenance(type, id, prov) | UPDATE {type} SET provenance = provenance \|\| new_entries WHERE sha256 LIKE '{id}%' |
| entities.count(type, **filters) | SELECT COUNT(*) FROM {type} WHERE [filters] |
| entities.find_by_hash(type, key) | SELECT FROM {type} WHERE sha256 LIKE '{key}%' LIMIT 1 |
| flags.write_flag(flag) | INSERT INTO curation_flags (...) |
| flags.read_flags(status, type) | SELECT FROM curation_flags WHERE [filters] |
| flags.resolve_flag(id, ...) | UPDATE curation_flags SET status=... WHERE id=... |
| runs.save_summary(summary) | INSERT INTO run_summaries (...) |
| runs.load_previous(source) | SELECT FROM run_summaries WHERE source=... ORDER BY started_at DESC LIMIT 1 |
| runs.list_runs(source, limit) | SELECT FROM run_summaries WHERE [source] ORDER BY started_at DESC LIMIT [limit] |

## Relay Cursor Pagination

```
cursor = base64(f"{created_at_iso}|{uuid}")

PageInfo:
  hasNextPage: bool
  endCursor: str | null

Connection:
  edges: [{cursor, node}]
  pageInfo: PageInfo
  totalCount: int
```
