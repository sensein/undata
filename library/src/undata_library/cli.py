"""CLI entry point for undata-library."""

from __future__ import annotations

import sys
from pathlib import Path

import click

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
