"""Command line entry point: `finance import statement.pdf`."""

from datetime import date
from pathlib import Path

import typer

from finance.categorization.seed import seed as seed_database
from finance.categorization.store import run_categorization
from finance.db import connection
from finance.evals.labels_io import export_labels, import_labels
from finance.evals.run import run_eval
from finance.ingestion.adapters import UnsupportedStatement
from finance.ingestion.importer import import_statement
from finance.settings import REPO_ROOT, get_settings

app = typer.Typer(help="personal-finance-agent command line", no_args_is_help=True)
labels_app = typer.Typer(
    help="Export or import your labels (the golden set).", no_args_is_help=True
)
app.add_typer(labels_app, name="labels")


@app.callback()
def main() -> None:
    """Keep `import` an explicit subcommand: Typer collapses a single-command app."""


@app.command("import")
def import_statements(files: list[Path] = typer.Argument(..., exists=True, readable=True)) -> None:
    """Import one or more PDF bank statements."""
    failed = False
    for path in files:
        try:
            with connection() as conn:
                summary = import_statement(path.read_bytes(), path.name, conn)
        except (UnsupportedStatement, ValueError) as error:
            typer.echo(f"{path.name}: {error}", err=True)
            failed = True
            continue
        typer.echo(
            f"{summary.filename}: {summary.bank} ····{summary.iban_last4} "
            f"total={summary.rows_total} new={summary.rows_new} duplicate={summary.rows_duplicate}"
        )
    try:
        typer.echo(run_categorization().line())
    except Exception as error:  # the import itself already succeeded
        typer.echo(f"categorization failed: {error!r}", err=True)
    if failed:
        raise typer.Exit(code=1)


@app.command("seed")
def seed_command() -> None:
    """Load the category taxonomy and system rules into the database."""
    with connection() as conn:
        categories, rules = seed_database(conn)
    typer.echo(f"categories={categories} rules={rules}")


@app.command("categorize")
def categorize_command(
    include_all: bool = typer.Option(
        False, "--all", help="Re-run every transaction you have not labelled yourself."
    ),
) -> None:
    """Categorize pending transactions (pairing, rules, jev)."""
    typer.echo(run_categorization(include_all).line())


@app.command("eval-categorization")
def eval_command(
    limit: int | None = typer.Option(None, min=1, help="Only the first N labelled transactions."),
    note: str = typer.Option("", help="What changed, for docs/evals/HISTORY.md."),
) -> None:
    """Benchmark the categorizer against your labels (dry run, writes nothing to the database)."""
    try:
        with connection() as conn:
            out = run_eval(conn, get_settings(), limit=limit, note=note)
    except RuntimeError as error:  # no jev key, or no golden row scored
        typer.echo(f"eval-categorization: {error}", err=True)
        raise typer.Exit(code=1) from error
    typer.echo((out / "report.md").read_text())
    typer.echo(f"saved to {out}")


@labels_app.command("export")
def labels_export(
    path: Path | None = typer.Argument(None),
    force: bool = typer.Option(False, "--force", help="Overwrite the file if it exists."),
) -> None:
    """Write your labels to CSV (default: data/labels/labels-YYYYMMDD.csv)."""
    target = path or REPO_ROOT / "data" / "labels" / f"labels-{date.today():%Y%m%d}.csv"
    try:
        with connection() as conn:
            count = export_labels(conn, target, overwrite=force)
    except FileExistsError as error:  # never replace a backup by accident
        typer.echo(
            f"labels export: {target} already exists; pass --force to overwrite it", err=True
        )
        raise typer.Exit(code=1) from error
    typer.echo(f"exported={count} to {target}")


@labels_app.command("import")
def labels_import(path: Path = typer.Argument(..., exists=True, readable=True)) -> None:
    """Load labels from CSV by dedup_key."""
    with connection() as conn:
        result = import_labels(conn, path)
    typer.echo(f"imported={result.imported} missing={result.missing}")
