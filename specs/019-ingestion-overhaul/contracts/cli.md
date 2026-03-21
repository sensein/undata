# CLI Contract: Ingestion Overhaul

## Modified Commands

### `undata-library ingest`

```
undata-library ingest --source SOURCE [--path PATH] [--library-path PATH]
    [--adapter ADAPTER]           # force adapter (json-schema, linkml, csv, code-repo, bids, nwb, dandi, openminds, aind)
    [--adapter-module MODULE]     # import path for third-party adapter
    [--workflow YAML]             # workflow spec file
    [--llm-model MODEL]          # litellm model spec (e.g., ollama/llama3, openai/gpt-4o)
    [--llm-threshold FLOAT]      # confidence threshold for LLM invocation (default: 0.7)
    [--docker]                    # enable Docker code inspection
    [--docker-image IMAGE]        # custom Docker base image
    [--docker-timeout SECONDS]    # container timeout (default: 300)
    [--strict]                    # exit 1 on any validation violation
    [--skip-validation]           # skip post-ingestion validation
```

**Output**: Ingestion stats + `ingestion-report.yaml`

### `undata-library pipeline`

Gains the same new flags as `ingest` plus existing `--skip-enrich` / `--skip-align`.

## New Commands

### `undata-library validate-ingestion`

```
undata-library validate-ingestion [PATH] [--strict]
```

Standalone post-hoc validation of library output. Checks:
- data_type validity on all elements
- sha256 integrity on all files
- URI uniqueness across all entity types
- Schema property references resolve
- ValueConcept references in response_options resolve
- No orphan ValueConcepts (not referenced by any element or valueset)

**Output**: `ingestion-report.yaml` + summary to stdout

## Adapter Interface Contract

```python
class BaseAdapter(ABC):
    @abstractmethod
    def extract(self, source_path: Path, **options) -> list[ClassifiedEntity]: ...

    @property
    @abstractmethod
    def name(self) -> str: ...

    @property
    def supported_formats(self) -> list[str]:
        return []
```

### ClassifiedEntity

```python
@dataclass
class ClassifiedEntity:
    entity_type: EntityType        # class | attribute | enum_value | valueset
    semantic: dict                 # raw semantic identity
    provenance: dict               # raw provenance
    confidence: float              # 0.0–1.0
    source_context: dict | None    # adapter metadata
```

### ClassifiedEntity JSON (Docker output format)

Docker inspection scripts write `result.json` containing a list of ClassifiedEntity:

```json
[
  {
    "entity_type": "attribute",
    "semantic": {"data_type": "string", "ontology_term": null},
    "provenance": {"source": "aind", "class": "Subject", "name": "age", "description": "Age"},
    "confidence": 0.95,
    "source_context": {"parent_class": "Subject", "field_type": "str"}
  }
]
```

## Workflow YAML Contract

See data-model.md WorkflowSpec for full schema.

## Ingestion Report Contract

Written to `ingestion-report.yaml` after every ingest run.
See data-model.md IngestionReport for full schema.
```yaml
generated_at: "2026-03-20T..."
sources_processed: 1
stats:
  elements_created: 150
  schemas_created: 12
  valuesets_created: 3
  values_created: 45
validation:
  passed: true
  violations: []
```
