"""CLI entry point for undata-library."""

from __future__ import annotations

import sys
from pathlib import Path

import click

import json

import asyncio

from .diff import diff_file
from .index import write_index
from .validation import validate_directory, validate_file


@click.group()
def main() -> None:
    """undata-library: manage neuroscience data elements and mappings."""


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

    if total_violations > 0 and strict:
        sys.exit(1)
    elif total_violations > 0:
        sys.exit(1)


@main.command()
@click.argument("file", type=click.Path(exists=True))
@click.option("--from", "from_version", type=int, default=None, help="Source version number")
@click.option("--to", "to_version", type=int, default=None, help="Target version number")
@click.option(
    "--format", "fmt", type=click.Choice(["text", "json"]), default="text", help="Output format"
)
def diff(file: str, from_version: int | None, to_version: int | None, fmt: str) -> None:
    """Show differences between element versions."""
    diffs = diff_file(Path(file), from_version, to_version)

    if not diffs:
        click.echo("No differences found (or fewer than 2 versions).")
        return

    if fmt == "json":
        click.echo(json.dumps([d.to_dict() for d in diffs], indent=2, default=str))
    else:
        for d in diffs:
            marker = " [BREAKING]" if d.breaking else ""
            click.echo(f"  {d.field}:{marker}")
            click.echo(f"    old: {d.old_value}")
            click.echo(f"    new: {d.new_value}")


@main.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--output", "-o", default="index.yaml", help="Output file path")
def index(path: str, output: str) -> None:
    """Build an index.yaml registry of all elements and mappings."""
    base = Path(path)
    out = base / output if not Path(output).is_absolute() else Path(output)
    idx = write_index(base, out)
    click.echo(
        f"Index written to {out}: "
        f"{idx['element_count']} elements, {idx['mapping_count']} mappings."
    )


@main.command("export")
@click.option("--backend-url", required=True, help="Backend API base URL")
@click.option("--output", "-o", default=".", help="Output directory")
@click.option("--token", envvar="API_TOKEN", help="Bearer token for auth")
def export_cmd(backend_url: str, output: str, token: str | None) -> None:
    """Export elements and mappings from backend to YAML files."""
    from .export import export_elements, export_mappings

    out = Path(output)
    el_count = asyncio.run(export_elements(backend_url, out / "elements", token))
    mp_count = asyncio.run(export_mappings(backend_url, out / "mappings", token))
    click.echo(f"Exported {el_count} elements and {mp_count} mappings to {out}.")


@main.command("import")
@click.option("--backend-url", required=True, help="Backend API base URL")
@click.option("--path", "-p", default="elements", help="Path to element YAML files")
@click.option("--token", envvar="API_TOKEN", help="Bearer token for auth")
def import_cmd(backend_url: str, path: str, token: str | None) -> None:
    """Import element YAML files to backend."""
    from .import_lib import import_elements

    created, skipped = asyncio.run(import_elements(backend_url, Path(path), token))
    click.echo(f"Imported {created} elements, skipped {skipped}.")
