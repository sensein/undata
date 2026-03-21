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
from .models import RegistryConfig
from .validation import validate_directory, validate_file


def get_output_dir(cli_value: str | None) -> Path:
    """Resolve output directory from CLI flag, env var, or XDG default."""
    return RegistryConfig.resolve(cli_value)


_ONTOLOGY_STORE_DIR = Path.home() / ".cache" / "undata" / "ontology-store"


def get_ontology_store_path() -> Path:
    """Ontology store lives in cache (rebuildable), not output dir."""
    _ONTOLOGY_STORE_DIR.mkdir(parents=True, exist_ok=True)
    return _ONTOLOGY_STORE_DIR


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
@click.option(
    "--source",
    required=True,
    help="Source name (bids, nwb, dandi, aind, openminds, json-schema, linkml, csv, code-repo)",
)
@click.option("--path", "-p", default=None, help="Path to raw schema files")
@click.option(
    "--output-dir",
    "-o",
    default=None,
    help="Output directory (default: ~/.local/share/undata/registry/)",
)
@click.option(
    "--adapter", default=None, help="Force adapter name (overrides --source for adapter selection)"
)
@click.option("--adapter-module", default=None, help="Import path for third-party adapter")
@click.option(
    "--workflow",
    "workflow_path",
    default=None,
    type=click.Path(exists=True),
    help="Workflow YAML file",
)
@click.option(
    "--llm-model", default=None, help="LLM model for classification (e.g., ollama/llama3)"
)
@click.option("--llm-threshold", default=0.7, help="Confidence threshold for LLM invocation")
@click.option("--docker", "docker_enabled", is_flag=True, help="Enable Docker code inspection")
@click.option("--docker-image", default=None, help="Custom Docker base image")
@click.option("--docker-timeout", default=300, help="Container timeout in seconds")
@click.option("--strict", is_flag=True, help="Exit 1 on any validation violation")
@click.option("--skip-validation", is_flag=True, help="Skip post-ingestion validation")
@click.option(
    "--version", "source_version", default=None, help="Pin source version (git tag/branch/SHA)"
)
@click.option("--refresh", is_flag=True, help="Force re-download even if cached")
@click.option("--offline", is_flag=True, help="Use only cached sources (no network)")
@click.option("--keep-envs", is_flag=True, help="Keep temporary venvs after extraction")
@click.option("--source-def", "source_def_path", default=None, help="Custom source definition YAML")
def ingest(
    source: str,
    path: str | None,
    output_dir: str | None,
    adapter: str | None,
    adapter_module: str | None,
    workflow_path: str | None,
    llm_model: str | None,
    llm_threshold: float,
    docker_enabled: bool,
    docker_image: str | None,
    docker_timeout: int,
    strict: bool,
    skip_validation: bool,
    source_version: str | None,
    refresh: bool,
    offline: bool,
    keep_envs: bool,
    source_def_path: str | None,
) -> None:
    """Ingest elements from raw schema files into the library."""
    resolved_dir = get_output_dir(output_dir)

    if workflow_path:
        from .workflow import load_workflow, run_workflow

        spec = load_workflow(Path(workflow_path))
        report = run_workflow(spec, resolved_dir)
        click.echo(
            f"Workflow complete: {report.sources_processed} sources, "
            f"{len(report.violations)} violations."
        )
        if strict and not report.validation_passed:
            sys.exit(1)
        return

    from .ingest import ingest_source

    schema_path = Path(path) if path else None
    adapter_name = adapter or source
    stats = ingest_source(adapter_name, schema_path, resolved_dir)
    click.echo(
        f"Ingested {source}: {stats['total']} unique elements "
        f"({stats['created']} created, {stats['merged']} merged)."
    )

    if not skip_validation:
        from .validation import validate_ingestion_output

        violations = validate_ingestion_output(resolved_dir)
        if violations:
            click.echo(f"Validation: {len(violations)} violations found.")
            for v in violations[:10]:
                click.echo(f"  {v['severity']}: {v['file']} — {v['message']}")
            if strict:
                sys.exit(1)
        else:
            click.echo("Validation: passed.")


@main.command("validate-ingestion")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--strict", is_flag=True, help="Exit 1 on any violation")
def validate_ingestion_cmd(path: str, strict: bool) -> None:
    """Validate library output: data_types, sha256, URI uniqueness, references."""
    from .validation import validate_ingestion_output

    violations = validate_ingestion_output(Path(path))
    if not violations:
        click.echo("Validation passed. 0 violations.")
        return

    for v in violations:
        click.echo(f"  {v['severity']}: {v['file']} — {v['message']}")
    click.echo(f"\n{len(violations)} violations found.")
    if strict:
        sys.exit(1)


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
    """Verify ontology alignment of elements against ontology store."""
    from .verify import verify_elements

    # Try OntologyStore first, fall back to legacy cache
    store_path = get_ontology_store_path()
    store = None
    cache = None
    if store_path.exists():
        from .ontology_store import OntologyStore

        store = OntologyStore(store_path)
    else:
        from .ontology_cache import OntologyCache

        cache = OntologyCache(Path(cache_dir))

    warnings = verify_elements(Path(path), store=store, cache=cache)

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
@click.option("--output-dir", default=None, help="Output directory")
@click.option("--exclude", multiple=True, help="Ontologies to skip (e.g., --exclude ncbitaxon)")
def ontology_refresh(ontology: str | None, output_dir: str | None, exclude: tuple) -> None:
    """Download ontologies from OBO Foundry and load into local store."""
    from .ontology_fetch import _download_obo
    from .ontology_store import OntologyStore, build_vector_index, load_ontology_config

    store = OntologyStore(get_ontology_store_path())
    configs = load_ontology_config()

    if ontology:
        configs = [c for c in configs if c["name"] == ontology]
    if exclude:
        configs = [c for c in configs if c["name"] not in exclude]

    for cfg in configs:
        name = cfg["name"]
        url = cfg["url"]
        fmt = cfg.get("format", "obo")
        click.echo(f"Fetching {name} ({fmt})...")
        try:
            dl_path = _download_obo(name, url)
            try:
                if fmt == "obo":
                    count = store.load_obo(name, dl_path)
                else:
                    # OWL/TTL/RDF-XML → load directly into pyoxigraph
                    count = store.load_rdf(name, dl_path, fmt)
                click.echo(f"  {name}: {count} terms loaded into store.")
            finally:
                dl_path.unlink(missing_ok=True)
        except Exception as exc:
            click.echo(f"  {name}: FAILED — {exc}")

    # Build vector index
    try:
        vectors_path = get_ontology_store_path().parent / "ontology-vectors.parquet"
        count = build_vector_index(store, vectors_path)
        click.echo(f"Vector index: {count} terms embedded.")
    except ImportError:
        click.echo("  (skipping vector index — sentence-transformers not installed)")
    except Exception as exc:
        click.echo(f"  Vector index failed: {exc}")


@ontology_group.command("search")
@click.argument("query")
@click.option("--ontology", "-o", default=None, help="Filter by ontology")
@click.option("--limit", "-l", default=20, help="Max results")
@click.option("--output-dir", default=None, help="Output directory")
def ontology_search(query: str, ontology: str | None, limit: int, output_dir: str | None) -> None:
    """Search ontology terms by label or synonym."""
    from .ontology_store import OntologyStore

    store = OntologyStore(get_ontology_store_path())
    results = store.search_terms(query, ontology=ontology, limit=limit)

    if not results:
        click.echo("No matching terms found.")
        return

    for r in results:
        click.echo(f"  {r['uri']}  {r['label']}")
    click.echo(f"\n{len(results)} results.")


@ontology_group.command("info")
@click.option("--output-dir", default=None, help="Output directory")
def ontology_info(output_dir: str | None) -> None:
    """Show loaded ontologies, term counts, and store status."""
    from .ontology_store import OntologyStore

    store_path = get_ontology_store_path()
    if not store_path.exists():
        click.echo("No ontology store found. Run `ontology refresh` first.")
        return

    store = OntologyStore(store_path)
    loaded = store.list_loaded()
    total = store.term_count()

    if not loaded:
        click.echo("No ontologies loaded.")
        return

    for ont in loaded:
        click.echo(
            f"  {ont['name']}: {ont['term_count']} terms (loaded {ont.get('loaded_at', '?')})"
        )
    click.echo(f"\nTotal: {total} terms across {len(loaded)} ontologies.")

    vectors = get_ontology_store_path().parent / "ontology-vectors.parquet"
    if vectors.exists():
        size_mb = vectors.stat().st_size / 1024 / 1024
        click.echo(f"Vector index: {size_mb:.1f} MB")
    else:
        click.echo("Vector index: not built")


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

    elem_path = Path(elements_path)
    lib_path = elem_path.parent if elem_path.name == "elements" else elem_path
    idx = build_ontology_index(elem_path, library_path=lib_path)
    out_path = Path(output)
    out_path.write_text(yaml.dump(idx, default_flow_style=False, sort_keys=False), encoding="utf-8")
    click.echo(
        f"Ontology index written to {out_path}: "
        f"{idx['ontology_term_count']} terms, {idx.get('entity_count', idx.get('element_count', 0))} entities."
    )


@main.command()
@click.option("--source", required=True, help="Source name (bids, nwb, dandi, aind, openminds)")
@click.option("--path", "-p", default=None, help="Path to raw schema files")
@click.option(
    "--output-dir",
    "-o",
    default=None,
    help="Output directory (default: ~/.local/share/undata/registry/)",
)
@click.option("--model", "-m", default="all-MiniLM-L6-v2", help="Embedding model name")
@click.option("--skip-enrich", is_flag=True, help="Skip enrichment step")
@click.option("--skip-align", is_flag=True, help="Skip alignment step")
def pipeline(
    source: str,
    path: str | None,
    output_dir: str | None,
    model: str,
    skip_enrich: bool,
    skip_align: bool,
) -> None:
    """Run ingest → enrich → align → transform pipeline."""
    import time

    from .align import align_elements
    from .enrich import enrich_elements
    from .ingest import ingest_source

    lib = get_output_dir(output_dir)
    schema_path = Path(path) if path else None
    elements_dir = lib / "elements"
    cache_dir = lib / "ontology-cache"
    timings: dict[str, float] = {}

    # Step 1: Ingest
    click.echo(f"[1/3] Ingesting {source}...")
    t0 = time.time()
    ingest_stats = ingest_source(source, schema_path, lib)
    timings["ingest"] = time.time() - t0
    click.echo(
        f"  {ingest_stats['total']} elements "
        f"({ingest_stats['created']} created, {ingest_stats['merged']} merged) "
        f"in {timings['ingest']:.1f}s"
    )

    # Step 2: Enrich
    enrich_stats: dict = {}
    if not skip_enrich:
        click.echo("[2/3] Enriching elements...")
        t0 = time.time()
        enrich_stats = enrich_elements(
            elements_dir=elements_dir,
            cache_dir=cache_dir,
            library_path=lib,
            model_name=model,
        )
        timings["enrich"] = time.time() - t0
        click.echo(
            f"  {enrich_stats.get('enriched_new', 0)} new, "
            f"{enrich_stats.get('enriched_unchanged', 0)} unchanged "
            f"in {timings['enrich']:.1f}s"
        )
    else:
        click.echo("[2/3] Enrichment skipped.")

    # Step 3: Align
    align_stats: dict = {}
    if not skip_align:
        click.echo("[3/3] Aligning elements...")
        t0 = time.time()
        align_stats = align_elements(
            elements_dir=elements_dir,
            library_path=lib,
        )
        timings["align"] = time.time() - t0
        click.echo(
            f"  {align_stats.get('total_pairs_evaluated', 0)} pairs, "
            f"{align_stats.get('exact_match_groups', 0)} exact groups "
            f"in {timings['align']:.1f}s"
        )
    else:
        click.echo("[3/4] Alignment skipped.")

    # Step 4: Transform
    if not skip_align:  # transforms depend on alignment
        click.echo("[4/4] Generating transforms...")
        t0 = time.time()
        from .transform import generate_transforms

        transform_stats = generate_transforms(
            elements_dir=elements_dir,
            library_path=lib,
        )
        timings["transform"] = time.time() - t0
        click.echo(
            f"  {transform_stats.get('transforms_created', 0)} transforms "
            f"in {timings['transform']:.1f}s"
        )
    else:
        click.echo("[4/4] Transforms skipped (requires alignment).")

    total_time = sum(timings.values())
    click.echo(f"\nPipeline complete in {total_time:.1f}s.")


@main.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--threshold", "-t", default=0.5, help="Alias detection threshold")
@click.option("--output", "-o", default=None, help="Output report file path")
@click.option("--dry-run", is_flag=True, help="Preview changes without writing")
def align(path: str, threshold: float, output: str | None, dry_run: bool) -> None:
    """Run alias detection, form groups, update provenance, produce alignment report."""
    from .align import align_elements

    base = Path(path)
    elements_dir = base / "elements" if (base / "elements").exists() else base
    output_path = Path(output) if output else None

    stats = align_elements(
        elements_dir=elements_dir,
        library_path=base,
        threshold=threshold,
        output_path=output_path,
        dry_run=dry_run,
    )

    prefix = "[DRY RUN] " if dry_run else ""
    click.echo(
        f"{prefix}Alignment: {stats['total_pairs_evaluated']} pairs evaluated, "
        f"{stats['exact_match_groups']} exact groups, "
        f"{stats['close_match_groups']} close groups "
        f"({stats['new_groups']} new, {stats['unchanged_groups']} unchanged, "
        f"{stats['dissolved_groups']} dissolved)."
    )


@main.command("transform")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--threshold", "-t", default=0.5, help="Minimum pattern confidence")
@click.option(
    "--output-dir", default=None, help="Output directory for transforms (default: transforms/)"
)
def transform_cmd(path: str, threshold: float, output_dir: str | None) -> None:
    """Generate transforms between overlapping elements."""
    from .transform import generate_transforms

    base = Path(path)
    elements_dir = base / "elements" if (base / "elements").exists() else base
    lib_path = base if (base / "elements").exists() else base.parent

    stats = generate_transforms(elements_dir, lib_path, threshold=threshold)
    click.echo(
        f"Transforms: {stats['pairs_evaluated']} pairs evaluated, "
        f"{stats['transforms_created']} created."
    )
    for pattern, count in stats.get("patterns", {}).items():
        if count > 0:
            click.echo(f"  {pattern}: {count}")


@main.command()
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--cache-dir", default="ontology-cache", help="Ontology cache directory")
@click.option("--threshold", "-t", default=0.7, help="Ontology assignment threshold")
@click.option("--model", "-m", default="all-MiniLM-L6-v2", help="Embedding model name")
@click.option("--dry-run", is_flag=True, help="Preview changes without writing")
def enrich(path: str, cache_dir: str, threshold: float, model: str, dry_run: bool) -> None:
    """Enrich elements: auto-assign ontology_term, resolve values, populate value_domain."""
    from .enrich import enrich_elements

    base = Path(path)
    elements_dir = base / "elements" if (base / "elements").exists() else base

    stats = enrich_elements(
        elements_dir=elements_dir,
        cache_dir=Path(cache_dir),
        library_path=base,
        model_name=model,
        threshold=threshold,
        dry_run=dry_run,
    )

    prefix = "[DRY RUN] " if dry_run else ""
    click.echo(
        f"{prefix}Enriched: {stats['total']} elements — "
        f"{stats['enriched_new']} new, {stats['enriched_unchanged']} unchanged, "
        f"{stats['ontology_assigned']} ontology assigned, "
        f"{stats['values_resolved']} values resolved, "
        f"{stats['value_domain_set']} value_domain set."
    )


@main.command("embed")
@click.argument("path", type=click.Path(exists=True), default=".")
@click.option("--model", "-m", default="all-MiniLM-L6-v2", help="Embedding model name")
@click.option("--include-ontology", is_flag=True, help="Also build ontology embeddings")
def embed_cmd(path: str, model: str, include_ontology: bool) -> None:
    """Build precomputed embeddings for elements (and optionally ontology terms)."""
    from .embeddings import build_element_embeddings, build_ontology_embeddings

    base = Path(path)
    elements_dir = base / "elements" if (base / "elements").exists() else base

    click.echo(f"Building element embeddings (model={model})...")
    store = build_element_embeddings(elements_dir, model_name=model)
    out = base / "embeddings.parquet"
    store.save(out, model_name=model)
    click.echo(f"  {store.size} elements → {out}")

    if include_ontology:
        cache_dir = base / "ontology-cache"
        if cache_dir.exists():
            click.echo("Building ontology embeddings...")
            onto_store = build_ontology_embeddings(cache_dir, model_name=model)
            onto_out = cache_dir / "embeddings.parquet"
            onto_store.save(onto_out, model_name=model)
            click.echo(f"  {onto_store.size} terms → {onto_out}")
        else:
            click.echo("  No ontology-cache/ found — skipping ontology embeddings.")


@main.group("cache")
def cache_group() -> None:
    """Manage the source cache."""


@cache_group.command("list")
def cache_list() -> None:
    """Show all cached sources."""
    from .acquisition import SourceCache

    cache = SourceCache()
    entries = cache.list_cached()
    if not entries:
        click.echo("No cached sources.")
        return
    for e in entries:
        click.echo(f"  {e['source']}/{e['version']}  {e['size_mb']}MB  {e['downloaded_at']}")
    click.echo(f"\n{len(entries)} cached sources.")


@cache_group.command("clean")
@click.option("--older-than", default=None, type=int, help="Remove sources older than N days")
def cache_clean(older_than: int | None) -> None:
    """Remove cached sources."""
    from .acquisition import SourceCache

    cache = SourceCache()
    removed = cache.clean(older_than_days=older_than)
    click.echo(f"Removed {removed} cached source(s).")
