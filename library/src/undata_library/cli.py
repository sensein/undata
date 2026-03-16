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
        f"{idx['element_count']} elements, {idx['schema_count']} schemas."
    )


@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option(
    "--format", "fmt", type=click.Choice(["text", "json"]), default="text",
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
