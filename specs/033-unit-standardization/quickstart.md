# Quickstart: 033 Unit Standardization Validation

## QS-001: QUDT vocabulary loads
```python
from undata_library.unit_resolver import UnitResolver
resolver = UnitResolver()
assert resolver.unit_count() >= 2800
```

## QS-002: Common units resolve
```python
result = resolver.resolve("kg")
assert result.uri == "http://qudt.org/vocab/unit/KiloGM"
assert result.label == "Kilogram"

result = resolver.resolve("years")
assert result.uri == "http://qudt.org/vocab/unit/YR"
```

## QS-003: Aliases resolve to same URI
```python
assert resolver.resolve("kg").uri == resolver.resolve("kilogram").uri
assert resolver.resolve("years").uri == resolver.resolve("yr").uri
```

## QS-004: Unresolved units return None
```python
result = resolver.resolve("wobbles")
assert result is None
```

## QS-005: Hash normalization works
```python
# Two elements with same semantics but different unit spelling
elem_a = {"semantic": {"data_type": "float", "unit": "kg"}}
elem_b = {"semantic": {"data_type": "float", "unit": "kilogram"}}
# After enrichment, both have unit_uri = qudt:KiloGM
# Hash uses unit_uri → same hash
```

## QS-006: Conversion factors available
```python
factor = resolver.conversion_factor("http://qudt.org/vocab/unit/YR", "http://qudt.org/vocab/unit/MO")
assert factor == 12.0
```

## QS-007: All existing tests pass
```bash
cd library && uv run pytest tests/ -v
# Expected: 400+ tests pass
```
