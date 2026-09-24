from datetime import datetime
from uuid import uuid4

from finance.evals.metrics import EvalRow, compute_metrics
from finance.evals.report import EvalMeta, history_line, render_markdown


def _row(golden, predicted, confidence, *, sub=None, flagged=False, merchant=None, named=None):
    level1 = {"groceries": "shopping", "fashion": "shopping", "restaurants_bars": "leisure"}
    return EvalRow(
        transaction_id=uuid4(),
        text="synthetic",
        outgoing=True,
        golden_slug=golden,
        golden_level1=level1[golden],
        golden_subscription=sub,
        golden_merchant=merchant,
        predicted_slug=predicted,
        predicted_level1=level1[predicted],
        confidence=confidence,
        level1_confidence=confidence,
        predicted_subscription=flagged,
        subscription_score=0.9 if flagged else 0.1,
        predicted_merchant=named,
    )


ROWS = [
    _row("groceries", "groceries", 0.99, sub=False, merchant="ACME", named="ACME"),
    _row("groceries", "fashion", 0.97, sub=False, merchant="ACME", named="ACME FOODS"),
    _row("restaurants_bars", "restaurants_bars", 0.6, sub=True, flagged=True),
    _row("fashion", "restaurants_bars", 0.4, sub=True),
]

META = EvalMeta(
    run_at=datetime(2026, 9, 24, 10, 0),
    model="jev-1.13.0",
    fingerprint="abcd1234",
    note="synthetic",
)


def test_accuracy_buckets_and_thresholds():
    metrics = compute_metrics(ROWS)
    assert (metrics.level2.right, metrics.level2.total) == (2, 4)
    assert metrics.level1.right == 3  # fashion vs groceries is still shopping: right at level 1
    top = [b for b in metrics.level2.buckets if b.low == 0.95][0]
    assert (top.rows, top.right) == (2, 1)
    at_95 = [t for t in metrics.level2.thresholds if t.threshold == 0.95][0]
    assert (at_95.accepted, at_95.wrong, at_95.review) == (2, 1, 2)


def test_subscription_and_merchant_scores():
    metrics = compute_metrics(ROWS)
    assert (metrics.subscription_precision.hits, metrics.subscription_precision.total) == (1, 1)
    assert (metrics.subscription_recall.hits, metrics.subscription_recall.total) == (1, 2)
    assert (metrics.merchant.hits, metrics.merchant.total) == (1, 2)


def test_report_and_history_line():
    metrics = compute_metrics(ROWS)
    assert "| 0.95 | 2 | 1 |" in render_markdown(META, metrics)
    line = history_line(META, metrics)
    assert line.startswith("| 2026-09-24 | eval | jev-1.13.0 | 4 | 50.0% | 75.0% | 50.0% | 2 |")
    assert line.count("|") == 11
    assert "failed" not in line


def test_rows_jev_failed_on_are_reported_in_the_note_cell():
    metrics = compute_metrics(ROWS)
    meta = META.model_copy(update={"failed": 2})
    assert "2 left out: jev failed" in render_markdown(meta, metrics)
    line = history_line(meta, metrics)
    assert line.endswith("| synthetic · failed=2 |")
    assert line.count("|") == 11  # still the ten columns of docs/evals/HISTORY.md


def test_a_note_cannot_break_the_history_table():
    meta = META.model_copy(update={"note": "wording | criteria\nround 2"})
    line = history_line(meta, compute_metrics(ROWS))
    assert line.endswith("| wording / criteria round 2 |")
    assert line.count("|") == 11 and "\n" not in line
