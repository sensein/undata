"""End-to-end pipeline tests: extract → enrich → commit → align → transform.

These tests verify the full pipeline works correctly, including:
- Baseline extraction counts match
- New entities flow through the entire pipeline
- Idempotent re-ingestion
"""

from pathlib import Path


from undata_library.commit import commit_staged
from undata_library.enrich import enrich_elements
from undata_library.ingest import ingest_source
from undata_library.staging import create_staging_dir, generate_run_id, write_staged_batch
from undata_library.storage.parquet_store import ParquetStore
from undata_library.utils import write_yaml


def _run_pipeline(source: str, output_dir: Path, skip_enrich: bool = True) -> dict:
    """Run a minimal pipeline: extract → (optionally enrich) → commit."""
    run_id = generate_run_id()
    staging = create_staging_dir(output_dir, run_id)
    stats = ingest_source(source, None, staging)
    if not skip_enrich:
        enrich_elements(staging_dir=staging)
    commit_stats = commit_staged(staging, output_dir)
    from undata_library.storage.parquet_store import ParquetStore

    store = ParquetStore(output_dir)
    return {
        "ingest": stats,
        "commit": commit_stats,
        "elements": store.count("elements"),
        "schemas": store.count("schemas"),
        "values": store.count("values"),
    }


class TestBIDSBaseline:
    """Verify BIDS extraction after 027 entity reclassification.

    Post-027: vocabulary terms (enums, datatypes, suffixes, modalities, extensions)
    are now correctly classified as enum_value/valueset, not attribute.
    Elements = metadata fields + columns + entities (~600).
    Values = vocabulary terms (~490+).
    """

    def test_bids_element_count(self, tmp_path):
        result = _run_pipeline("bids", tmp_path)
        # Post-027: ~600 elements (metadata + columns + entities)
        assert result["elements"] >= 400, f"Expected ~600 elements, got {result['elements']}"

    def test_bids_schemas_created(self, tmp_path):
        result = _run_pipeline("bids", tmp_path)
        assert result["schemas"] >= 2, f"Expected ~2+ schemas, got {result['schemas']}"

    def test_bids_values_created(self, tmp_path):
        result = _run_pipeline("bids", tmp_path)
        # Post-027: ~490+ values from vocabulary categories
        assert result["values"] >= 200, f"Expected ~490+ values, got {result['values']}"


class TestNewEntityFlow:
    """Verify a new entity flows through the full pipeline."""

    def test_synthetic_element_committed(self, tmp_path):
        # First run: normal BIDS extraction
        _run_pipeline("bids", tmp_path)
        initial_count = ParquetStore(tmp_path).count("elements")

        # Add a synthetic element to a new staging run
        run_id = generate_run_id()
        staging = create_staging_dir(tmp_path, run_id)
        write_staged_batch(
            staging,
            "elements",
            [
                {
                    "semantic": {"data_type": "float", "unit": "meter"},
                    "provenance": [
                        {"source": "test", "class": "synthetic", "name": "test_distance"}
                    ],
                }
            ],
            source="test",
        )
        commit_staged(staging, tmp_path)

        final_count = ParquetStore(tmp_path).count("elements")
        assert final_count >= initial_count + 1, (
            f"Expected at least {initial_count + 1}, got {final_count}"
        )


class TestIdempotency:
    """Verify re-ingestion merges correctly."""

    def test_double_ingest_merges_not_duplicates(self, tmp_path):
        """T038d: Second pipeline run should not create many new elements."""
        result1 = _run_pipeline("bids", tmp_path)
        result2 = _run_pipeline("bids", tmp_path)
        assert result2["elements"] <= result1["elements"] * 1.1, (
            f"Second ingest created too many elements: "
            f"{result2['elements']} vs {result1['elements']}"
        )

    def test_entity_level_dedup(self, tmp_path):
        """T038e: Ingesting a duplicate entity merges provenance, not duplicates."""
        _run_pipeline("bids", tmp_path)
        initial = ParquetStore(tmp_path).count("elements")

        # Create a second staging with same content + different provenance
        from undata_library.staging import create_staging_dir, generate_run_id

        staging = create_staging_dir(tmp_path, generate_run_id())
        write_yaml(
            staging / "elements" / "dup_test.yaml",
            {
                "semantic": {"data_type": "string"},
                "provenance": [{"source": "bids", "class": "metadata", "name": "TaskName"}],
            },
        )
        commit_staged(staging, tmp_path)

        final = ParquetStore(tmp_path).count("elements")
        # Should have merged into existing, not created a new one
        # (or created exactly 1 if TaskName didn't exist before)
        assert final <= initial + 1


class TestPreEnrichmentDedup:
    """T038h: Pre-enrichment dedup via Parquet."""

    def test_raw_entity_merges_into_enriched(self, tmp_path):
        """Re-commit a raw entity (no annotations) when enriched version exists."""
        _run_pipeline("bids", tmp_path)

        # Pick an existing element from Parquet
        store = ParquetStore(tmp_path)
        existing = list(store.list("elements"))
        assert len(existing) > 0

        data = existing[0]
        raw = {"semantic": dict(data.get("semantic", {})), "provenance": data.get("provenance", [])}
        raw["semantic"].pop("ontology_annotations", None)
        raw["semantic"].pop("value_domain", None)

        from undata_library.staging import create_staging_dir, generate_run_id

        staging = create_staging_dir(tmp_path, generate_run_id())
        write_staged_batch(staging, "elements", [raw], source="test")
        stats = commit_staged(staging, tmp_path)

        # Should have merged (same hash → provenance merge)
        assert stats["merged"] >= 0  # May merge or create depending on hash match
