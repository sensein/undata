# Quickstart: 011-metamodel-provenance

**Date**: 2026-03-12

---

## Scenario 1 — Create an Object-Typed Element with schema_ref

```python
import httpx

BASE = "http://localhost:8002/api/v1"
HEADERS = {"Authorization": "Bearer qs005testtoken1234567890abcdef1234567890abcdef1234567890abcdef12"}

# 1. Create a schema to use as the type
address_schema = httpx.post(f"{BASE}/schemas", json={
    "name": "AddressSchema",
    "description": "Postal address",
}, headers=HEADERS).raise_for_status().json()

# 2. Create a source
source = httpx.post(f"{BASE}/sources", json={
    "name": "quickstart-source", "format": "json"
}, headers=HEADERS).raise_for_status().json()

# 3. Create an object-typed element with schema_ref
element = httpx.post(f"{BASE}/elements", json={
    "source_id": source["id"],
    "source_local_id": "user.address",
    "name": "address",
    "value_type": "object",
    "schema_ref": address_schema["id"],  # required for object type
}, headers=HEADERS).raise_for_status().json()

assert element["value_type"] == "object"
assert element["schema_ref"] == address_schema["id"]
```

---

## Scenario 2 — Query Provenance for a DataElement

```python
# Continue from Scenario 1

resp = httpx.get(
    f"{BASE}/elements/{element['id']}/provenance",
    headers={**HEADERS, "Accept": "application/ld+json"}
).raise_for_status().json()

# Verify PROV-O structure
assert resp["@context"] == "https://www.w3.org/ns/prov.jsonld"
assert any(n.get("@type") == "prov:Entity" for n in resp["@graph"])
assert any(n.get("@type") == "prov:Activity" for n in resp["@graph"])
assert any(n.get("@type") == "prov:Agent" for n in resp["@graph"])
```

---

## Scenario 3 — Export Schema as LinkML

```python
resp = httpx.get(
    f"{BASE}/schemas/{address_schema['id']}/linkml",
    headers={**HEADERS, "Accept": "application/yaml"}
)
resp.raise_for_status()

fidelity = float(resp.headers["X-Roundtrip-Fidelity"])
assert fidelity > 0.0

linkml_yaml = resp.text
assert "classes:" in linkml_yaml
```

---

## Scenario 4 — Import Schema from LinkML

```python
linkml_payload = """
id: https://undata.org/schemas/example-import
name: ExampleImport
prefixes:
  linkml: https://w3id.org/linkml/
imports:
  - linkml:types
classes:
  ExampleImport:
    slots:
      - value
slots:
  value:
    range: string
"""

resp = httpx.post(
    f"{BASE}/schemas/import/linkml",
    content=linkml_payload,
    headers={**HEADERS, "Content-Type": "application/yaml"}
).raise_for_status().json()

assert "schema_id" in resp
assert 0.0 <= resp["fidelity_score"] <= 1.0
assert isinstance(resp["loss_points"], list)
```

---

## Scenario 5 — Accept a Pending Mapping via Confidence Threshold

```python
# Assume a system-inferred mapping exists
pending = httpx.get(
    f"{BASE}/mappings",
    params={"status": "pending_curation"},
    headers=HEADERS
).raise_for_status().json()

if pending["items"]:
    m = pending["items"][0]
    resp = httpx.put(
        f"{BASE}/mappings/{m['id']}/accept",
        params={"confidence_threshold": 0.7},
        headers=HEADERS
    )
    if m.get("confidence_score", 0) >= 0.7:
        assert resp.status_code == 200
        assert resp.json()["status"] == "active"
    else:
        assert resp.status_code == 422
```

---

## Scenario 6 — Generate Meta-model Documentation

```bash
cd /path/to/undata
uv run gen-doc docs/undata-metamodel.yaml -d docs/site/metamodel/
ls docs/site/metamodel/index.md  # must exist
```

---

## Offline Validation

These checks run without a live backend (CI-friendly):

```bash
# Validate PROV-O LinkML YAML
cd backend
uv run linkml-lint data/prov-o.linkml.yaml

# Validate meta-model YAML
uv run linkml-lint docs/undata-metamodel.yaml

# Validate gen-doc runs
uv run gen-doc docs/undata-metamodel.yaml -d /tmp/metamodel-docs/
```
