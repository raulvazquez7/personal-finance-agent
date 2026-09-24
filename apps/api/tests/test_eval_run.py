import asyncio
import json
from contextlib import contextmanager
from datetime import date

import pytest

from finance.categorization.categorizer import CategorizationContext
from finance.categorization.labels import confirm_merchant, label_transaction
from finance.categorization.rules import load_rules
from finance.categorization.taxonomy import load_taxonomy
from finance.evals import run
from finance.evals.run import evaluate, run_eval
from finance.settings import Settings
from tests.fakes import FakeJev, jev_result

pytestmark = pytest.mark.integration

ACME = jev_result(
    merchant={"ZZTEST ACME": 0.99, "none": 0.01},
    category={"groceries": 0.97, "restaurants_bars": 0.03},
)


@pytest.fixture(autouse=True)
def no_real_jev(monkeypatch):
    """A real jev client would bill every golden row: tests pass a fake."""

    def _refuse(*args, **kwargs):
        raise AssertionError("tests must replace TypesafeJev with a fake")

    monkeypatch.setattr(run, "TypesafeJev", _refuse)


def _written(conn):
    return conn.execute(
        "select (select count(*) from transaction_labels) as labels,"
        " (select count(*) from merchants) as merchants"
    ).fetchone()


def test_dry_run_scores_user_labels_without_merchant_defaults(db_conn, make_tx):
    tx = make_tx("-9.90", "PAGO | ZZTEST ACME", merchant="ZZTEST ACME")
    label_transaction(db_conn, tx, "restaurants_bars", False, new_merchant_name="ZZTEST ACME")
    merchant = db_conn.execute(
        "select merchant_id from transactions where id = %s", (tx,)
    ).fetchone()["merchant_id"]
    confirm_merchant(db_conn, merchant, "restaurants_bars", False)
    before = _written(db_conn)

    jev = FakeJev(first={"ZZTEST ACME": ACME})
    ctx = CategorizationContext(load_taxonomy(db_conn), load_rules(db_conn), Settings())
    rows, model, failed = asyncio.run(evaluate(db_conn, ctx, jev))

    mine = next(row for row in rows if row.transaction_id == tx)
    assert (mine.golden_slug, mine.predicted_slug) == ("restaurants_bars", "groceries")
    assert (model, failed) == ("jev-test", 0)
    assert _written(db_conn) == before  # a dry run writes nothing
    row = db_conn.execute(
        "select category_slug, category_source from transactions where id = %s", (tx,)
    ).fetchone()
    assert (row["category_slug"], row["category_source"]) == ("restaurants_bars", "user")


class SpanRecorder:
    """Stands in for the Langfuse client: records the spans run_eval opens."""

    def __init__(self) -> None:
        self.names: list[str] = []
        self.open = False

    @contextmanager
    def start_as_current_observation(self, *, as_type: str, name: str):
        self.names.append(f"{as_type}:{name}")
        self.open = True
        try:
            yield self
        finally:
            self.open = False

    def update(self, **kwargs) -> None:
        pass


class TracedFakeJev(FakeJev):
    """FakeJev as run_eval builds TypesafeJev; notes whether each call ran inside the span."""

    def __init__(self, span: SpanRecorder, **kwargs) -> None:
        super().__init__(**kwargs)
        self.span = span
        self.inside: list[bool] = []
        self.input_tokens = 0

    async def __aenter__(self) -> "TracedFakeJev":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        pass

    async def ask(self, name: str, state: dict, questions: dict):
        self.inside.append(self.span.open)
        self.input_tokens += 100
        return await super().ask(name, state, questions)


def test_run_eval_writes_the_report_and_one_history_line_in_one_eval_trace(
    db_conn, make_tx, tmp_path, monkeypatch
):
    ok = make_tx("-9.90", "PAGO | ZZTEST ACME", merchant="ZZTEST ACME")
    broken = make_tx("-4.00", "PAGO | ZZTEST BROKEN", merchant="ZZTEST BROKEN")
    for tx in (ok, broken):
        label_transaction(db_conn, tx, "groceries", False)
    span = SpanRecorder()
    jev = TracedFakeJev(
        span, first={"ZZTEST ACME": ACME, "ZZTEST BROKEN": RuntimeError("jev is down")}
    )
    built = {}

    def _build(api_key, concurrency, tags):
        built.update(concurrency=concurrency, tags=tags)
        return jev

    monkeypatch.setattr(run, "TypesafeJev", _build)
    monkeypatch.setattr(run, "langfuse", lambda: span)
    history = tmp_path / "HISTORY.md"
    history.write_text("| Date | Source |\n|---|---|\n")
    before = _written(db_conn)

    settings = Settings(typesafe_api_key="sk-fake", jev_concurrency=3)
    out = run_eval(db_conn, settings, note="synthetic", out_root=tmp_path / "out", history=history)

    assert built == {"concurrency": 3, "tags": ["eval"]}
    assert span.names == ["span:eval"] and jev.inside and all(jev.inside)
    last = history.read_text().splitlines()[-1]
    assert last.startswith(f"| {date.today():%Y-%m-%d} | eval | jev-test |")
    assert last.endswith("| synthetic · failed=1 |")
    assert "1 left out: jev failed" in (out / "report.md").read_text()
    rows_csv = (out / "rows.csv").read_text()
    assert str(ok) in rows_csv and str(broken) not in rows_csv
    summary = json.loads((out / "summary.json").read_text())
    assert summary["meta"]["failed"] == 1
    assert _written(db_conn) == before
