"""undata CLI — neuroscience schema integration tool."""

from __future__ import annotations

import asyncio
import json

import typer

from undata.logging import get_logger

app = typer.Typer(
    name="undata",
    help="Integrate neuroscience schemas (BIDS, DANDI, openMINDS, NWB).",
    no_args_is_help=True,
)

logger = get_logger(__name__)

_KNOWN_SOURCES = ("bids", "dandi", "openminds", "nwb", "aind")
_ADAPTERS_REQUIRING_PATH = {"bids", "dandi", "nwb", "openminds"}


def _get_adapter(source: str):
    s = source.lower()
    if s == "bids":
        from undata.adapters.bids import BIDSAdapter

        return BIDSAdapter()
    if s == "dandi":
        from undata.adapters.dandi import DANDIAdapter

        return DANDIAdapter()
    if s == "openminds":
        from undata.adapters.openminds import OpenMINDSAdapter

        return OpenMINDSAdapter()
    if s == "nwb":
        from undata.adapters.nwb import NWBAdapter

        return NWBAdapter()
    if s == "aind":
        from undata.adapters.aind import AINDAdapter

        return AINDAdapter()
    raise typer.BadParameter(f"Unknown source: {source!r}. Known: {_KNOWN_SOURCES}")


def _load_adapter(adapter, extraction_mode: str, source_path: str) -> None:
    """Call the appropriate dual-path loader based on extraction_mode."""
    source_lower = adapter.source_name.lower()
    if extraction_mode in ("file", "both") and not source_path:
        if source_lower in _ADAPTERS_REQUIRING_PATH:
            raise typer.BadParameter(
                f"--source-path is required when --extraction-mode={extraction_mode} "
                f"for {adapter.source_name}"
            )

    if extraction_mode == "code":
        adapter.load_code()
    elif extraction_mode == "file":
        adapter.load_file(source_path)
    else:  # "both"
        adapter.load_code()
        adapter.load_file(source_path)


@app.command()
def ingest(
    sources: list[str] = typer.Argument(..., help='Sources: "bids", "dandi", "openminds", "nwb"'),
    backend_url: str = typer.Option(
        "http://localhost:8002/api/v1", "--backend-url", envvar="UNDATA_BACKEND_URL"
    ),
    token: str | None = typer.Option(None, "--token", envvar="UNDATA_TOKEN"),
    version_tag: str | None = typer.Option(None, "--version-tag"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    output_format: str = typer.Option("text", "--output-format"),
    log_level: str = typer.Option("INFO", "--log-level"),
    extraction_mode: str = typer.Option(
        "code",
        "--extraction-mode",
        help='Extraction mode: "code" (library introspection), "file" (schema files), "both".',
    ),
    source_path: str = typer.Option(
        "",
        "--source-path",
        help="Path to schema files (required when --extraction-mode=file or both).",
    ),
) -> None:
    """Ingest schema sources and push normalized elements to the backend."""
    import logging

    if extraction_mode not in ("code", "file", "both"):
        typer.echo(
            f"Error: --extraction-mode must be one of: code, file, both. Got: {extraction_mode!r}",
            err=True,
        )
        raise typer.Exit(2)

    if not token and not dry_run:
        typer.echo("Error: --token / UNDATA_TOKEN is required for live ingest.", err=True)
        raise typer.Exit(2)
    if not token:
        token = "dry-run-placeholder"

    logging.getLogger("undata").setLevel(log_level.upper())

    from undata.ingestion import IngestionPipeline

    pipeline = IngestionPipeline(backend_url=backend_url, token=token)

    results = []
    exit_code = 0

    for source in sources:
        try:
            adapter = _get_adapter(source)
            _load_adapter(adapter, extraction_mode, source_path)
            elements = adapter.extract_elements(extraction_mode)
            version_info = adapter.get_version_info()
            if version_tag:
                version_info["version_tag"] = version_tag

            result = asyncio.run(
                pipeline.ingest(
                    source_name=adapter.source_name,
                    source_format=adapter.source_format,
                    elements=elements,
                    version_info=version_info,
                    dry_run=dry_run,
                )
            )
            results.append(result)
            if result.elements_failed:
                exit_code = max(exit_code, 1)
        except Exception as exc:
            typer.echo(f"Fatal error ingesting {source}: {exc}", err=True)
            exit_code = 2

    total_succeeded = sum(r.elements_succeeded for r in results)
    total_failed = sum(r.elements_failed for r in results)
    total_duration = sum(r.duration_seconds for r in results)

    if output_format == "json":
        out = {
            "results": [
                {
                    "source": r.source_name,
                    "succeeded": r.elements_succeeded,
                    "failed": r.elements_failed,
                    "duration_s": round(r.duration_seconds, 2),
                }
                for r in results
            ],
            "total_succeeded": total_succeeded,
            "total_failed": total_failed,
        }
        typer.echo(json.dumps(out))
    else:
        for r in results:
            status = "✓" if r.elements_failed == 0 else "✗"
            typer.echo(
                f"{status} {r.source_name}: {r.elements_succeeded} succeeded, "
                f"{r.elements_failed} failed ({r.duration_seconds:.1f}s)"
            )
        typer.echo(
            f"Total: {total_succeeded} elements ingested"
            + (f", {total_failed} failed" if total_failed else "")
            + f" in {total_duration:.1f}s"
        )

    raise typer.Exit(exit_code)


@app.command("detect-aliases")
def detect_aliases(
    backend_url: str = typer.Option(
        "http://localhost:8002/api/v1", "--backend-url", envvar="UNDATA_BACKEND_URL"
    ),
    token: str | None = typer.Option(None, "--token", envvar="UNDATA_TOKEN"),
    threshold: float = typer.Option(0.92, "--threshold"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    output_format: str = typer.Option("text", "--output-format"),
    source_filter: str | None = typer.Option(None, "--source-filter"),
) -> None:
    """Detect alias pairs and register identity mappings."""
    if not token:
        token = ""

    from undata.alias_detection import AliasDetector

    sources = [s.strip() for s in source_filter.split(",")] if source_filter else None
    detector = AliasDetector(
        backend_url=backend_url,
        token=token,
        threshold=threshold,
        dry_run=dry_run,
        source_filter=sources,
    )
    candidates = asyncio.run(detector.detect())

    if output_format == "sssom-tsv":
        typer.echo(detector.to_sssom_tsv(candidates))
    elif output_format == "json":
        import json as _json

        typer.echo(
            _json.dumps(
                [
                    {
                        "element_a_id": c.element_a_id,
                        "element_b_id": c.element_b_id,
                        "similarity_score": c.similarity_score,
                        "predicate": c.predicate,
                        "detection_method": c.detection_method,
                    }
                    for c in candidates
                ]
            )
        )
    else:
        exact = [c for c in candidates if c.predicate == "skos:exactMatch"]
        close = [c for c in candidates if c.predicate == "skos:closeMatch"]
        typer.echo(f"Detected alias pairs (threshold={threshold}):")
        for c in candidates:
            kind = "EXACT" if c.predicate == "skos:exactMatch" else "CLOSE"
            typer.echo(
                f"  {kind}  {c.element_a_id} ↔ {c.element_b_id}"
                f"  [score={c.similarity_score:.2f}, {c.predicate}]"
            )
        action = "candidates found" if dry_run else "registered"
        typer.echo(f"Total: {len(exact)} exact matches, {len(close)} close matches {action}.")


@app.command("generate-schema")
def generate_schema(
    backend_url: str = typer.Option(
        "http://localhost:8002/api/v1", "--backend-url", envvar="UNDATA_BACKEND_URL"
    ),
    output: str | None = typer.Option(None, "--output"),
    schema_id: str = typer.Option("https://undata.org/schema/neuroscience", "--schema-id"),
    schema_name: str = typer.Option("NeuroscienceUnified", "--schema-name"),
    version: str | None = typer.Option(None, "--version"),
    include_sources: str | None = typer.Option(None, "--include-sources"),
    fmt: str = typer.Option("yaml", "--format"),
) -> None:
    """Generate a unified LinkML schema from backend elements."""
    from undata.linkml_gen import LinkMLSchemaGenerator

    sources = [s.strip() for s in include_sources.split(",")] if include_sources else None
    gen = LinkMLSchemaGenerator(
        backend_url=backend_url,
        schema_id=schema_id,
        schema_name=schema_name,
        version=version,
    )
    schema = asyncio.run(gen.generate(include_sources=sources))
    yaml_str = gen.to_yaml(schema)

    if output:
        with open(output, "w") as fh:
            fh.write(yaml_str)
        typer.echo(f"Schema written to {output}", err=True)
    else:
        typer.echo(yaml_str)


@app.command()
def validate(
    data_file: str = typer.Argument(..., help="Path to JSON or YAML data file"),
    schema: str | None = typer.Option(None, "--schema"),
    target_class: str = typer.Option("NeuroscienceDataset", "--target-class"),
    output_format: str = typer.Option("text", "--output-format"),
) -> None:
    """Validate a data file against the unified LinkML schema."""
    import json as _json

    from undata.validation import ValidationService

    # Load data file
    try:
        with open(data_file) as fh:
            content = fh.read()
        try:
            record = _json.loads(content)
        except _json.JSONDecodeError:
            import yaml as _yaml

            record = _yaml.safe_load(content)
    except Exception as exc:
        typer.echo(f"Error reading data file: {exc}", err=True)
        raise typer.Exit(2)

    svc = ValidationService(schema_path=schema, target_class=target_class)
    report = svc.validate(record)

    if output_format == "json":
        typer.echo(svc.to_json(report))
    else:
        typer.echo(svc.to_text(report))

    raise typer.Exit(0 if report["status"] == "PASS" else 1)


if __name__ == "__main__":
    app()
