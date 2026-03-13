# Quickstart: End-to-End Schema Ingestion and LinkML Export

**Feature**: `007-end-to-end-pipeline` | **Date**: 2026-03-11

---

## Prerequisites

- Docker and Docker Compose (for backend + PostgreSQL)
- `uv` (Python package manager)
- `git`, `curl` (for fetch-schemas.sh)
- Backend running: `cd backend && docker compose up -d`

---

## Validation Checklist

### QS-001: Dependency Installation

```bash
cd ingestion
uv sync
uv run python -c "import pynwb; print('pynwb', pynwb.__version__)"
uv run python -c "import openminds; print('openminds OK')"
```
Expected: both print without error.
Fallback if pynwb fails: `uv run undata ingest nwb --extraction-mode file --source-path schemas/nwb/`
Fallback if openMINDS fails: `uv run undata ingest openminds --extraction-mode file --source-path schemas/openminds/`

---

### QS-002: Adapter Self-Test (no backend needed)

```bash
cd ingestion
uv run python -c "
from undata.adapters.bids import BIDSAdapter
from undata.adapters.dandi import DANDIAdapter
from undata.adapters.nwb import NWBAdapter
from undata.adapters.openminds import OpenMINDSAdapter
from undata.adapters.aind import AINDAdapter

bids = BIDSAdapter(); bids.load_code()
print('BIDS:', len(bids.extract_elements('code')), 'elements (expect ≥400)')

dandi = DANDIAdapter(); dandi.load_code()
print('DANDI:', len(dandi.extract_elements('code')), 'elements (expect ≥100)')

nwb = NWBAdapter(); nwb.load_code()
print('NWB:', len(nwb.extract_elements('code')), 'elements (expect ≥200)')

om = OpenMINDSAdapter(); om.load_code()
print('openMINDS:', len(om.extract_elements('code')), 'elements (expect ≥500)')

aind = AINDAdapter(); aind.load_file('')
print('AIND:', len(aind.extract_elements('file')), 'elements (expect ≥50)')
"
```
Expected: all print with counts meeting or exceeding the parenthetical expectations.

---

### QS-003: Schema Download

```bash
cd ingestion
bash scripts/fetch-schemas.sh
ls schemas/nwb/*.yaml | wc -l   # expect 13
ls schemas/openminds/ | wc -l   # expect ≥292 .schema.omi.json files
ls schemas/aind/*.json | wc -l  # expect ≥9
```

---

### QS-004: Clean Database Setup

```bash
cd backend
docker compose up -d db backend
# Wait for backend to be healthy
until curl -s http://localhost:8002/health | grep -q '"status":"ok"'; do sleep 2; done
echo "Backend ready"
```

---

### QS-005: Full Ingest (requires live backend)

```bash
cd ingestion
export UNDATA_BACKEND_URL=http://localhost:8002/api/v1
export UNDATA_TOKEN=<curator-token>

# Code-path (BIDS, DANDI, NWB, openMINDS)
uv run undata ingest bids dandi nwb openminds --extraction-mode code

# File-path (AIND — Python 3.14 incompatible for code-path)
uv run undata ingest aind --extraction-mode file
```

Verify via API:
```bash
curl -s http://localhost:8002/api/v1/sources | python3 -c "
import json,sys; d=json.load(sys.stdin)
for s in d['items']: print(s['name'], s.get('element_count','?'))
"
# Expect: bids, dandi, nwb, openMINDS, aind all listed with element_count ≥ 0

curl -s 'http://localhost:8002/api/v1/elements?limit=1' | python3 -c \
  "import json,sys; d=json.load(sys.stdin); print('Total elements:', d['total'])"
# Expect: total ≥ 1000
```

---

### QS-006: LinkML Export with Inheritance

```bash
cd ingestion
uv run undata generate-schema --output unified.yaml

# Check file is non-empty and has expected classes
grep "is_a: NeuroscienceDataset" unified.yaml | wc -l  # expect ≥5
grep "mixin: true" unified.yaml                         # expect ≥1 hit (ProvenanceMixin)
grep "mixins:" unified.yaml                             # expect ≥1 hit
grep "^  is_a:" unified.yaml | wc -l                   # expect multiple hits
```

---

### QS-007: LinkML Validation

```bash
# Install linkml (dev only, not runtime)
cd ingestion
uv add --dev linkml

# Validate
uv run linkml-validate --schema unified.yaml
# Expect: exit code 0, no errors reported
```

---

### QS-008: One-Command Pipeline

```bash
cd ingestion
make pipeline
```
Expected: all targets complete, exit code 0, `unified.yaml` exists and is valid.

---

### QS-009: Idempotency Check

```bash
cd ingestion
make pipeline   # first run (already completed above)
make pipeline   # second run — should handle 409 duplicate sources gracefully
echo "Exit code: $?"  # expect 0
```

---

### QS-010: Existing Tests Still Pass

```bash
cd ingestion
uv run pytest tests/ -q
# Expect: 132+ passed, 0 failed
```
