# Quickstart: Neuroscience Schema Integration
**Feature**: 001-neuro-schema-integration | **Date**: 2026-03-07

## Prerequisites

- 002-schema-backend running and healthy (`curl http://localhost:8002/health`)
- Python 3.12 with `uv` or `pip`
- Backend auth token set: `export UNDATA_TOKEN=<token>`

---

## 1. Install

```bash
uv pip install -e "ingestion/[all]"
```

---

## 2. Ingest all four schemas (dry run first)

```bash
undata ingest bids dandi openminds nwb --dry-run
# Expected: element counts per source, 0 failures, no writes
```

```bash
undata ingest bids dandi openminds nwb
# Expected: total ~500–1000 elements ingested
```

---

## 3. Detect aliases

```bash
undata detect-aliases --dry-run --output-format sssom-tsv > candidates.tsv
# Review candidates.tsv; re-run without --dry-run to register

undata detect-aliases
```

---

## 4. Generate the unified LinkML schema

```bash
undata generate-schema --output unified.yaml
# Validate with linkml tools:
linkml-validate -s unified.yaml --target-class NeuroscienceDataset /dev/null
```

---

## 5. Validate a sample data file

```bash
cat > sample.json <<'EOF'
{ "subject_age": 28, "session_id": "ses-01", "task_name": "rest" }
EOF

undata validate sample.json
# Expected: PASS
```

---

## Validation Checklist

- [ ] `undata ingest bids --dry-run` reports > 0 elements with 0 failures
- [ ] Full ingest of all four sources completes without fatal errors
- [ ] Backend `GET /elements?limit=10` returns ingested elements with correct provenance
- [ ] Alias detection identifies at least one `skos:exactMatch` pair
- [ ] `unified.yaml` passes `linkml-validate` schema lint with 0 errors
- [ ] A conformant JSON data file passes `undata validate`
- [ ] A data file with a missing required field fails `undata validate` with a clear error message
