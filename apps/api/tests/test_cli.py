from contextlib import nullcontext
from uuid import uuid4

from typer.testing import CliRunner

from finance import cli
from finance.ingestion.adapters import UnsupportedStatement
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


def _summary(filename: str) -> ImportSummary:
    return ImportSummary(
        import_id=uuid4(),
        account_id=uuid4(),
        bank="bbva",
        iban_last4="1332",
        filename=filename,
        rows_total=1,
        rows_new=1,
        rows_duplicate=0,
    )


def _pdfs(tmp_path, *names):
    paths = []
    for name in names:
        path = tmp_path / name
        path.write_bytes(b"%PDF-1.4 fake")
        paths.append(str(path))
    return paths


def test_import_reports_a_bad_file_and_continues_with_the_rest(tmp_path, monkeypatch):
    def fake_import(_bytes, name, _conn):
        if name == "broken.pdf":
            raise UnsupportedStatement("No adapter recognises this statement")
        return _summary(name)

    monkeypatch.setattr(cli, "connection", lambda: nullcontext(None))
    monkeypatch.setattr(cli, "import_statement", fake_import)

    result = runner.invoke(cli.app, ["import", *_pdfs(tmp_path, "a.pdf", "broken.pdf", "c.pdf")])

    assert result.exit_code == 1
    assert "a.pdf: bbva" in result.stdout
    assert "c.pdf: bbva" in result.stdout
    assert "broken.pdf: No adapter recognises this statement" in result.stderr


def test_import_exits_zero_when_every_file_imports(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "connection", lambda: nullcontext(None))
    monkeypatch.setattr(cli, "import_statement", lambda _bytes, name, _conn: _summary(name))

    result = runner.invoke(cli.app, ["import", *_pdfs(tmp_path, "a.pdf", "b.pdf")])

    assert result.exit_code == 0
    assert result.stderr == ""
