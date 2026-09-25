from contextlib import nullcontext
from datetime import date
from uuid import uuid4

import pytest
from typer.testing import CliRunner

from finance import cli
from finance.categorization.store import CategorizeSummary
from finance.evals.labels_io import LabelsImport
from finance.ingestion.adapters import UnsupportedStatement
from finance.models import ImportSummary

runner = CliRunner()


@pytest.fixture(autouse=True)
def no_real_categorization(monkeypatch):
    """`finance import` categorizes afterwards: never against the real ledger from a unit test."""
    monkeypatch.setattr(
        cli, "run_categorization", lambda include_all=False, rules_only=False: CategorizeSummary()
    )


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


def test_import_succeeds_even_when_categorization_fails(monkeypatch, tmp_path):
    pdf = tmp_path / "statement.pdf"
    pdf.write_bytes(b"%PDF")
    summary = ImportSummary(
        import_id="00000000-0000-0000-0000-000000000001",
        account_id="00000000-0000-0000-0000-000000000002",
        bank="bbva",
        iban_last4="0001",
        filename="statement.pdf",
        rows_total=1,
        rows_new=1,
        rows_duplicate=0,
    )

    class _Conn:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    def _fail(include_all=False):
        raise RuntimeError("jev is down")

    monkeypatch.setattr(cli, "connection", lambda: _Conn())
    monkeypatch.setattr(cli, "import_statement", lambda *args: summary)
    monkeypatch.setattr(cli, "run_categorization", _fail)
    result = runner.invoke(cli.app, ["import", str(pdf)])
    assert result.exit_code == 0
    assert "new=1" in result.output
    assert "categorization failed: RuntimeError('jev is down')" in result.output


def test_categorize_all_reruns_everything_and_prints_the_counts(monkeypatch):
    calls = []

    def _run(include_all=False, rules_only=False):
        calls.append((include_all, rules_only))
        return CategorizeSummary(
            paired=1, categorized=3, needs_review=1, by_source={"rule": 1, "jev": 2}
        )

    monkeypatch.setattr(cli, "run_categorization", _run)
    result = runner.invoke(cli.app, ["categorize", "--all"])
    assert result.exit_code == 0 and calls == [(True, False)]
    assert "paired=1 categorized=3 jev=2 rule=1 needs_review=1" in result.stdout


def test_categorize_says_why_it_skipped(monkeypatch):
    skipped = CategorizeSummary(paired=2, skipped="TYPESAFE_API_KEY is not set")
    monkeypatch.setattr(
        cli, "run_categorization", lambda include_all=False, rules_only=False: skipped
    )
    result = runner.invoke(cli.app, ["categorize"])
    assert result.stdout.strip() == (
        "jev skipped: TYPESAFE_API_KEY is not set (paired=2 categorized=0 needs_review=0)"
    )


def test_categorize_reports_rows_jev_could_not_answer(monkeypatch):
    partial = CategorizeSummary(categorized=2, by_source={"jev": 2}, failed=1)
    monkeypatch.setattr(
        cli, "run_categorization", lambda include_all=False, rules_only=False: partial
    )
    result = runner.invoke(cli.app, ["categorize"])
    assert result.stdout.strip() == "paired=0 categorized=2 jev=2 needs_review=0 failed=1"


def test_eval_categorization_passes_its_options_and_prints_the_report(monkeypatch, tmp_path):
    calls = []

    def _run_eval(conn, settings, limit=None, note=""):
        calls.append((limit, note))
        (tmp_path / "report.md").write_text("# Categorization eval")
        return tmp_path

    monkeypatch.setattr(cli, "connection", lambda: nullcontext(None))
    monkeypatch.setattr(cli, "run_eval", _run_eval)
    result = runner.invoke(cli.app, ["eval-categorization", "--limit", "5", "--note", "wording"])
    assert result.exit_code == 0 and calls == [(5, "wording")]
    assert "# Categorization eval" in result.stdout
    assert f"saved to {tmp_path}" in result.stdout


def test_eval_categorization_rejects_a_limit_below_one(monkeypatch):
    calls = []
    monkeypatch.setattr(cli, "connection", lambda: nullcontext(None))
    monkeypatch.setattr(cli, "run_eval", lambda *args, **kwargs: calls.append(args))
    result = runner.invoke(cli.app, ["eval-categorization", "--limit", "0"])
    assert result.exit_code == 2 and calls == []


def test_eval_categorization_shows_why_nothing_was_scored(monkeypatch):
    def _run_eval(conn, settings, limit=None, note=""):
        raise RuntimeError("no golden rows scored (3 failed)")

    monkeypatch.setattr(cli, "connection", lambda: nullcontext(None))
    monkeypatch.setattr(cli, "run_eval", _run_eval)
    result = runner.invoke(cli.app, ["eval-categorization"])
    assert result.exit_code == 1
    assert "no golden rows scored (3 failed)" in result.stderr


def test_labels_export_defaults_to_a_dated_file_under_data_labels(monkeypatch, tmp_path):
    targets = []
    monkeypatch.setattr(cli, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(cli, "connection", lambda: nullcontext(None))
    monkeypatch.setattr(
        cli, "export_labels", lambda conn, path, overwrite=False: targets.append(path) or 3
    )
    result = runner.invoke(cli.app, ["labels", "export"])
    assert result.exit_code == 0
    expected = tmp_path / "data" / "labels" / f"labels-{date.today():%Y%m%d}.csv"
    assert targets == [expected]
    assert result.stdout.strip() == f"exported=3 to {expected}"


class _LabelRows:
    """A connection whose one query returns these label rows."""

    def __init__(self, rows):
        self.rows = rows

    def execute(self, _sql):
        return self

    def fetchall(self):
        return self.rows


LABEL = {
    "dedup_key": "k1",
    "category_slug": "groceries",
    "is_subscription": False,
    "merchant": "ZZTEST ACME",
}


def test_labels_export_never_overwrites_an_existing_backup(monkeypatch, tmp_path):
    target = tmp_path / "labels.csv"
    target.write_text("the good backup\n")
    monkeypatch.setattr(cli, "connection", lambda: nullcontext(_LabelRows([])))
    result = runner.invoke(cli.app, ["labels", "export", str(target)])
    assert result.exit_code == 1
    assert f"{target} already exists; pass --force to overwrite it" in result.stderr
    assert target.read_text() == "the good backup\n"


def test_labels_export_with_force_overwrites_the_file(monkeypatch, tmp_path):
    target = tmp_path / "labels.csv"
    target.write_text("the old backup\n")
    monkeypatch.setattr(cli, "connection", lambda: nullcontext(_LabelRows([LABEL])))
    result = runner.invoke(cli.app, ["labels", "export", str(target), "--force"])
    assert result.exit_code == 0 and result.stdout.strip() == f"exported=1 to {target}"
    assert target.read_text().splitlines() == [
        "dedup_key,category_slug,is_subscription,merchant,note",
        "k1,groceries,False,ZZTEST ACME,",
    ]


def test_labels_import_prints_the_counts(monkeypatch, tmp_path):
    source = tmp_path / "labels.csv"
    source.write_text("dedup_key,category_slug,is_subscription,merchant\n")
    monkeypatch.setattr(cli, "connection", lambda: nullcontext(None))
    monkeypatch.setattr(
        cli, "import_labels", lambda conn, path: LabelsImport(imported=2, missing=1)
    )
    result = runner.invoke(cli.app, ["labels", "import", str(source)])
    assert result.exit_code == 0 and result.stdout.strip() == "imported=2 missing=1 notes=0"


def test_labels_import_exits_one_and_prints_bad_rows(monkeypatch, tmp_path):
    source = tmp_path / "labels.csv"
    source.write_text("dedup_key,category_slug,is_subscription,merchant\n")
    monkeypatch.setattr(cli, "connection", lambda: nullcontext(None))
    monkeypatch.setattr(
        cli,
        "import_labels",
        lambda conn, path: LabelsImport(imported=1, missing=0, errors=["line 3: unknown category"]),
    )
    result = runner.invoke(cli.app, ["labels", "import", str(source)])
    assert result.exit_code == 1
    assert "line 3: unknown category" in result.stderr


def test_categorize_rules_only_passes_the_flag(monkeypatch):
    calls = []

    def _run(include_all=False, rules_only=False):
        calls.append((include_all, rules_only))
        return CategorizeSummary(categorized=1, by_source={"rule": 1})

    monkeypatch.setattr(cli, "run_categorization", _run)
    result = runner.invoke(cli.app, ["categorize", "--all", "--rules-only"])
    assert result.exit_code == 0 and calls == [(True, True)]
