"""Command line entry point: `finance import statement.pdf`."""

from pathlib import Path

import typer

from finance.db import connection
from finance.ingestion.adapters import UnsupportedStatement
from finance.ingestion.importer import import_statement

app = typer.Typer(help="personal-finance-agent command line", no_args_is_help=True)


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
    if failed:
        raise typer.Exit(code=1)
