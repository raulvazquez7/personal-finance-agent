"""Readable outputs of a benchmark run: report.md and one line of docs/evals/HISTORY.md."""

from datetime import datetime

from pydantic import BaseModel

from finance.evals.metrics import LevelMetrics, Metrics

ACCEPT = 0.95


class EvalMeta(BaseModel):
    run_at: datetime
    model: str
    fingerprint: str
    note: str = ""
    input_tokens: int = 0
    failed: int = 0  # golden rows jev failed on: left out of every metric


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{value:.1%}"


def _level_tables(name: str, level: LevelMetrics) -> list[str]:
    lines = [
        f"## {name}: {level.right}/{level.total} = {_pct(level.accuracy())}",
        "",
        "| Confidence | Rows | Right |",
        "|---|---|---|",
    ]
    for b in level.buckets:
        right = _pct(b.right / b.rows) if b.rows else "—"
        lines.append(f"| {b.low:.2f}–{min(b.high, 1):.2f} | {b.rows} | {right} |")
    lines += ["", "| Threshold | Accepted | Wrong | Precision | Review |", "|---|---|---|---|---|"]
    for t in level.thresholds:
        lines.append(
            f"| {t.threshold:.2f} | {t.accepted} | {t.wrong} | {_pct(t.precision())} | {t.review} |"
        )
    return lines + [""]


def render_markdown(meta: EvalMeta, metrics: Metrics) -> str:
    cost = meta.input_tokens * 0.042 / 1_000_000
    failed = f" · {meta.failed} left out: jev failed" if meta.failed else ""
    lines = [
        f"# Categorization eval {meta.run_at:%Y-%m-%d %H:%M}",
        "",
        f"jev `{meta.model}` · taxonomy and rules `{meta.fingerprint}` · {metrics.rows} golden rows"
        f"{failed} · about ${cost:.3f}" + (f" · {meta.note}" if meta.note else ""),
        "",
        "jev varies by about ten rows between identical runs; smaller differences are noise.",
        "",
    ]
    lines += _level_tables("Level 2", metrics.level2) + _level_tables("Level 1", metrics.level1)
    sp, sr, m = metrics.subscription_precision, metrics.subscription_recall, metrics.merchant
    lines += [
        "## Subscriptions and merchants",
        "",
        f"- Subscription precision {sp.hits}/{sp.total}, recall {sr.hits}/{sr.total}"
        " (noul > 0.7, expenses)",
        f"- Merchant name right {m.hits}/{m.total} (same match key)",
        "",
    ]
    return "\n".join(lines)


def history_line(meta: EvalMeta, metrics: Metrics) -> str:
    at = metrics.level2.at(ACCEPT)
    sp, sr = metrics.subscription_precision, metrics.subscription_recall
    # The failed count rides in the note cell, so the table keeps its ten columns.
    failed = f"failed={meta.failed}" if meta.failed else ""
    # A pipe or a line break in the note would break the Markdown table.
    typed = " ".join(meta.note.replace("|", "/").split())
    note = " · ".join(part for part in (typed, failed) if part)
    cells = [
        f"{meta.run_at:%Y-%m-%d}",
        "eval",
        meta.model,
        str(metrics.rows),
        _pct(metrics.level2.accuracy()),
        _pct(metrics.level1.accuracy()),
        _pct(at.precision()),
        str(at.review),
        f"{sp.hits}/{sp.total} · {sr.hits}/{sr.total}",
        note,
    ]
    return "| " + " | ".join(cells) + " |"
