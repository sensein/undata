# Quickstart: 034 AI-Assisted Curation Interface

## QS-001: Flag review shows full evidence
```
Open /curation → expand a flag → see:
- Entity's current fields (data_type, unit, description)
- Reason for the flag (displayed prominently)
- Match candidates with scores (if available)
- Recommended action
```

## QS-002: Entity editor works
```
From a flag → click "Edit Entity" → right panel shows editable fields
Change unit from "years" to "months" → see diff (red: years, green: months)
Click "Save" → entity updated
```

## QS-003: LLM suggests ontology annotation
```
Open chat panel → entity context loaded
Type: "What ontology term best matches this element?"
LLM calls lookup_ontology_term → proposes annotation
Diff shows: added ontology_annotation with URI, label, score
Curator clicks "Apply" → annotation saved
```

## QS-004: Split-panel layout
```
Open /curation/chat → split view: chat (left) + editor (right)
Drag divider → panels resize
```

## QS-005: Chat-driven update
```
Type: "change the unit of this element to milliseconds"
LLM calls propose_entity_change → diff appears in right panel
Curator reviews → clicks "Apply"
```

## QS-006: Chat-driven ingestion
```
Type: "ingest source at https://github.com/example/schema using the BIDS adapter"
LLM calls trigger_ingestion → shows stats (N elements, N schemas extracted)
Curator reviews staged entities → clicks "Commit"
```

## QS-007: Batch curation
```
Type: "set unit=milliseconds for all EEG timing elements"
LLM proposes changes for 5 elements → diff shows all changes
Curator reviews → clicks "Apply All"
```
