from contextlib import nullcontext
from uuid import uuid4

from typer.testing import CliRunner

from finance import cli
from finance.models import ImportSummary

runner = CliRunner()


def test_import_prints_one_summary_line_per_file(tmp_path, monkeypatch):
    pdf = tmp_path / "statement.pdf"
    pdf.write_bytes(b"%PDF-1.4 fake")
    summary = ImportSummary(
        import_id=uuid4(),
        account_id=uuid4(),
        bank="bbva",
        iban_last4="1332",
        filename="statement.pdf",
        rows_total=10,
        rows_new=7,
        rows_duplicate=3,
    )
    monkeypatch.setattr(cli, "connection", lambda: nullcontext(None))
    monkeypatch.setattr(cli, "import_statement", lambda _bytes, _name, _conn: summary)

    result = runner.invoke(cli.app, ["import", str(pdf)])

    assert result.exit_code == 0
    assert "statement.pdf: bbva ····1332 total=10 new=7 duplicate=3" in result.output
