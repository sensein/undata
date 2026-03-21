"""CLI entry point for undata-library v2."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import click
import yaml

from .hashing import (
    build_element_uri,
    build_schema_uri,
    canonical_json,
    compute_sha256,
    generate_short_key,
)
from .validation import validate_directory, validate_file


@click.group()
def main() -> None:
    """undata-library: content-addressed neuroscience data element registry."""


@main.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--strict", is_flag=True, help="Exit 1 on any violation")
def validate(path: str, strict: bool) -> None:
    """Validate YAML files against the library schema."""
    target = Path(path)

    if target.is_file():
        reports = [validate_file(target)]
    else:
        reports = validate_directory(target)

    if not reports:
        click.echo("No YAML files found.")
        sys.exit(1)

    total_violations = 0
    for report in reports:
        if report.valid:
            click.echo(f"  OK  {report.path}")
        else:
            click.echo(f"  FAIL  {report.path}")
            for v in report.violations:
                click.echo(f"    {v.severity}: {v.field} — {v.message}")
                total_violations += 1

    click.echo(f"\n{len(reports)} files checked, {total_violations} violations.")

    if total_violations > 0:
        sys.exit(1)


@main.command("hash")
@click.argument("file", type=click.Path(exists=True))
def hash_cmd(file: str) -> None:
    """Compute and display the content hash for a YAML file."""
    data = yaml.safe_load(Path(file).read_text(encoding="utf-8"))

    if not isinstance(data, dict) or "semantic" not in data:
        click.echo("Error: file must contain a 'semantic' block.", err=True)
        sys.exit(1)

    semantic = data["semantic"]

    # Determine if element or schema
    if "properties" in semantic:
        record_type = "schema"
        canonical = canonical_json(semantic)
        sha = compute_sha256(canonical)
        key = generate_short_key(sha)
        name = data.get("provenance", [{}])[0].get("name", "unknown")
        uri = build_schema_uri(name, key)
    else:
        record_type = "element"
        canonical = canonical_json(semantic)
        sha = compute_sha256(canonical)
        key = generate_short_key(sha)
        name = data.get("provenance", [{}])[0].get("name", "unknown")
        uri = build_element_uri(name, key)

    click.echo(f"type:      {record_type}")
    click.echo(f"attribute: {name}")
    click.echo(f"key:       {key}")
    click.echo(f"sha256:    {sha}")
    click.echo(f"uri:       {uri}")
    click.echo(f"canonical: {canonical}")


@main.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--output", "-o", default="index.yaml", help="Output file path")
def index(path: str, output: str) -> None:
    """Build an index.yaml registry of all elements and schemas."""
    from .index import write_index

    base = Path(path)
    out = base / output if not Path(output).is_absolute() else Path(output)
    idx = write_index(base, out)
    click.echo(
        f"Index written to {out}: "
        f"{idx['element_count']} elements, {idx['schema_count']} schemas, "
        f"{idx.get('value_count', 0)} values."
    )


@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["text", "json"]),
    default="text",
)
def diff(file: str, fmt: str) -> None:
    """Show provenance differences in an element file."""
    from .diff import diff_provenance

    diffs = diff_provenance(Path(file))

    if not diffs:
        click.echo("Single provenance entry — nothing to diff.")
        return

    if fmt == "json":
        click.echo(json.dumps(diffs, indent=2, default=str))
    else:
        for d in diffs:
            click.echo(f"  {d['field']}:")
            click.echo(f"    {d['source_a']} → {d['value_a']}")
            click.echo(f"    {d['source_b']} → {d['value_b']}")


@main.command()
@click.option("--source", required=True, help="Source name (bids, nwb, dandi, aind, openminds)")
@click.option("--path", "-p", default=None, help="Path to raw schema files")
@click.option("--library-path", "-l", default=".", help="Path to library root")
def ingest(source: str, path: str | None, library_path: str) -> None:
    """Ingest elements from raw schema files into the library."""
    from .ingest import ingest_source

    schema_path = Path(path) if path else None
    stats = ingest_source(source, schema_path, Path(library_path))
    click.echo(
        f"Ingested {source}: {stats['total']} unique elements "
        f"({stats['created']} created, {stats['merged']} merged)."
    )


@main.command("export")
@click.option("--backend-url", required=True, help="Backend API base URL")
@click.option("--output", "-o", default=".", help="Output directory")
@click.option("--token", envvar="API_TOKEN", help="Bearer token for auth")
def export_cmd(backend_url: str, output: str, token: str | None) -> None:
    """Export elements, values, and schemas from backend to v2 YAML files."""
    import asyncio

    from .export import export_elements, export_schemas, export_values

    out = Path(output)
    el = asyncio.run(export_elements(backend_url, out / "elements", token))
    val = asyncio.run(export_values(backend_url, out / "values", token))
    sch = asyncio.run(export_schemas(backend_url, out / "schemas", token))
    click.echo(f"Exported {el} elements, {val} values, {sch} schemas to {out}.")


@main.command("import")
@click.option("--backend-url", required=True, help="Backend API base URL")
@click.option("--path", "-p", default=".", help="Path to library root")
@click.option("--token", envvar="API_TOKEN", help="Bearer token for auth")
def import_cmd(backend_url: str, path: str, token: str | None) -> None:
    """Import v2 YAML files to backend."""
    import asyncio

    from .import_lib import import_elements, import_schemas, import_values

    lib = Path(path)
    el_c, el_m = asyncio.run(import_elements(backend_url, lib / "elements", token))
    val_c, val_m = asyncio.run(import_values(backend_url, lib / "values", token))
    sch_c, sch_m = asyncio.run(import_schemas(backend_url, lib / "schemas", token))
    click.echo(
        f"Imported: {el_c} elements created, {el_m} merged; "
        f"{val_c} values created, {val_m} merged; "
        f"{sch_c} schemas created, {sch_m} merged."
    )


@main.command()
@click.argument("path", type=click.Path(exists=True), default="elements")
@click.option("--cache-dir", default="ontology-cache", help="Ontology cache directory")
def verify(path: str, cache_dir: str) -> None:
    """Verify ontology alignment of elements against offline cache."""
    from .ontology_cache import OntologyCache
    from .verify import verify_elements

    cache = OntologyCache(Path(cache_dir))
    warnings = verify_elements(Path(path), cache)

    if not warnings:
        click.echo("All ontology terms verified. 0 warnings.")
        return

    for w in warnings:
        click.echo(f"  {w['severity']}: {w['file']} — {w['issue']}")

    click.echo(f"\n{len(warnings)} warnings found.")
    sys.exit(1 if any(w["severity"] == "WARNING" for w in warnings) else 0)


@main.group("ontology")
def ontology_group() -> None:
    """Manage the ontology term cache."""


@ontology_group.command("refresh")
@click.option(
    "--ontology",
    "-o",
    default=None,
    help="Specific ontology to refresh (ncit, pato, hp, obi, ncbitaxon)",
)
@click.option("--cache-dir", default="ontology-cache", help="Cache directory")
@click.option("--max-terms", default=5000, help="Max terms per ontology")
def ontology_refresh(ontology: str | None, cache_dir: str, max_terms: int) -> None:
    """Fetch/update ontology terms from OLS API."""
    from .ontology_cache import OntologyCache
    from .ontology_fetch import SUPPORTED_ONTOLOGIES, fetch_ontology

    cache = OntologyCache(Path(cache_dir))
    targets = [ontology] if ontology else list(SUPPORTED_ONTOLOGIES.keys())

    for name in targets:
        click.echo(f"Fetching {name}...")
        try:
            data = fetch_ontology(name, max_terms=max_terms)
            cache.save(name, data)
            click.echo(f"  {name}: {len(data.get('terms', {}))} terms cached.")
        except Exception as exc:
            click.echo(f"  {name}: FAILED — {exc}")


@main.command("similarity")
@click.argument("file_a", type=click.Path(exists=True))
@click.argument("file_b", type=click.Path(exists=True))
def similarity_cmd(file_a: str, file_b: str) -> None:
    """Compute similarity between two element files."""
    from .similarity import compute_similarity

    data_a = yaml.safe_load(Path(file_a).read_text(encoding="utf-8"))
    data_b = yaml.safe_load(Path(file_b).read_text(encoding="utf-8"))

    result = compute_similarity(data_a, data_b)

    click.echo(f"Score:    {result['score']}")
    click.echo(f"Relation: {result['relation']}")
    click.echo("Components:")
    for k, v in result["components"].items():
        click.echo(f"  {k}: {v}")


@main.command("detect-aliases")
@click.argument("path", type=click.Path(exists=True), default="elements")
@click.option("--threshold", "-t", default=0.5, help="Minimum similarity score")
@click.option("--limit", "-l", default=50, help="Max candidates to show")
@click.option("--format", "fmt", type=click.Choice(["text", "yaml"]), default="text")
def detect_aliases_cmd(path: str, threshold: float, limit: int, fmt: str) -> None:
    """Detect alias candidates by semantic similarity."""
    from .alias_detection import detect_aliases

    click.echo(f"Scanning {path} for alias candidates (threshold={threshold})...")
    candidates = detect_aliases(Path(path), threshold=threshold)

    if not candidates:
        click.echo("No alias candidates found.")
        return

    shown = candidates[:limit]
    if fmt == "yaml":
        click.echo(yaml.dump(shown, default_flow_style=False))
    else:
        for c in shown:
            click.echo(
                f"  {c['score']:.3f} {c['relation']:20s} {c['element_a']} ↔ {c['element_b']}"
            )

    click.echo(f"\n{len(candidates)} candidates (showing top {len(shown)}).")

    # `annotate` command removed — element-mappings.yaml is no longer used.
    # Ontology annotations are tracked as curation provenance entries.
    # Use `ontology-index` to explore ontology → element relationships.


@main.command("ontology-index")
@click.argument("elements_path", type=click.Path(exists=True), default="elements")
@click.option("--output", "-o", default="ontology-index.yaml", help="Output file")
def ontology_index_cmd(elements_path: str, output: str) -> None:
    """Build a reverse index: ontology_term → element URIs."""
    from .index import build_ontology_index

    idx = build_ontology_index(Path(elements_path))
    out_path = Path(output)
    out_path.write_text(yaml.dump(idx, default_flow_style=False, sort_keys=False), encoding="utf-8")
    click.echo(
        f"Ontology index written to {out_path}: "
        f"{idx['ontology_term_count']} terms, {idx['element_count']} elements."
    )
