"""Dry run of the production categorizer against the user's labels (spec 13.1)."""

import asyncio
import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from psycopg import Connection

from finance.categorization.categorizer import CategorizationContext, categorize
from finance.categorization.jev_client import Jev, TypesafeJev
from finance.categorization.merchants import MerchantRoster
from finance.categorization.models import Categorization, TxInput
from finance.categorization.pairing import PairCandidate, find_pairs
from finance.categorization.rules import load_rules
from finance.categorization.taxonomy import Taxonomy, load_taxonomy
from finance.evals.metrics import EvalRow, compute_metrics
from finance.evals.report import EvalMeta, history_line, render_markdown
from finance.settings import REPO_ROOT, Settings
from finance.tracing import langfuse

# The golden set: the latest user label of each transaction.
_GOLDEN = """
select distinct on (l.transaction_id) l.transaction_id as id, l.category_slug, l.is_subscription,
       m.name as golden_merchant, a.bank, t.booked_at, t.amount, t.description_raw,
       t.bank_concept, t.merchant
from transaction_labels l
join transactions t on t.id = l.transaction_id
join accounts a on a.id = t.account_id
left join merchants m on m.id = l.merchant_id
where l.source = 'user'
order by l.transaction_id, l.labeled_at desc
"""


def fingerprint(ctx: CategorizationContext) -> str:
    """Categories in position order: jev sees its options in that order, so it is part of what
    a run measures."""
    payload = json.dumps(
        [c.model_dump() for c in ctx.taxonomy.categories()] + [r.model_dump() for r in ctx.rules],
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:8]


def _eval_row(golden: dict, result: Categorization, taxonomy: Taxonomy) -> EvalRow:
    return EvalRow(
        transaction_id=golden["id"],
        text=(f"{golden['bank_concept']} | " if golden["bank_concept"] else "")
        + (golden["merchant"] or ""),
        outgoing=golden["amount"] < 0,
        golden_slug=golden["category_slug"],
        golden_level1=taxonomy.get(golden["category_slug"]).level1,
        golden_subscription=golden["is_subscription"],
        golden_merchant=golden["golden_merchant"],
        predicted_slug=result.category_slug,
        predicted_level1=taxonomy.get(result.category_slug).level1,
        confidence=result.category_confidence,
        level1_confidence=result.level1_confidence,
        predicted_subscription=result.is_subscription,
        subscription_score=result.subscription_score,
        predicted_merchant=result.merchant_name,
    )


async def evaluate(
    conn: Connection, ctx: CategorizationContext, jev: Jev, limit: int | None = None
) -> tuple[list[EvalRow], str, int]:
    """Scored rows, the jev version, and how many golden rows jev failed on (not scored)."""
    golden = conn.execute(_GOLDEN).fetchall()[:limit]
    everything = conn.execute(
        "select id, account_id, booked_at, amount, description_raw from transactions"
    ).fetchall()
    pairs = find_pairs(
        [PairCandidate.model_validate(r) for r in everything],
        ctx.settings.transfer_pattern,
        ctx.settings.transfer_window_days,
    )
    pair_of = {}
    for out_id, in_id in pairs:
        pair_of[out_id] = pair_of[in_id] = uuid4()
    rows = [TxInput.model_validate(g | {"transfer_pair_id": pair_of.get(g["id"])}) for g in golden]
    # No merchant defaults and an empty roster: they come from the labels being scored.
    results = await categorize(rows, ctx, jev, MerchantRoster([]), use_merchant_defaults=False)
    # categorize leaves out the rows jev failed on, so results are matched by transaction id.
    by_id = {r.transaction_id: r for r in results}
    scored = [_eval_row(g, by_id[g["id"]], ctx.taxonomy) for g in golden if g["id"] in by_id]
    model = next((r.model for r in results if r.model), "no jev call")
    return scored, model, len(golden) - len(scored)


def run_eval(
    conn: Connection,
    settings: Settings,
    limit: int | None = None,
    note: str = "",
    out_root: Path = REPO_ROOT / "eval-output",
    history: Path = REPO_ROOT / "docs" / "evals" / "HISTORY.md",
) -> Path:
    if not settings.typesafe_api_key:
        raise RuntimeError("TYPESAFE_API_KEY is not set")
    ctx = CategorizationContext(load_taxonomy(conn), load_rules(conn), settings)

    async def _run() -> tuple[list[EvalRow], str, int, int]:
        # One trace per run: every jev generation nests under this span, tagged `eval`.
        with langfuse().start_as_current_observation(as_type="span", name="eval") as span:
            async with TypesafeJev(
                settings.typesafe_api_key, concurrency=settings.jev_concurrency, tags=["eval"]
            ) as jev:
                rows, model, failed = await evaluate(conn, ctx, jev, limit)
            span.update(output={"rows": len(rows), "failed": failed})
        return rows, model, failed, jev.input_tokens

    rows, model, failed, tokens = asyncio.run(_run())
    if not rows:  # no user labels, or jev failed on every row: nothing worth recording
        raise RuntimeError(f"no golden rows scored ({failed} failed)")
    metrics = compute_metrics(rows)
    meta = EvalMeta(
        run_at=datetime.now(),
        model=model,
        fingerprint=fingerprint(ctx),
        note=note,
        input_tokens=tokens,
        failed=failed,
    )
    out = out_root / f"{meta.run_at:%Y%m%d-%H%M%S}"
    out.mkdir(parents=True)
    with (out / "rows.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(EvalRow.model_fields))
        writer.writeheader()
        writer.writerows(row.model_dump() for row in rows)
    summary = {"meta": meta.model_dump(mode="json"), "metrics": metrics.model_dump()}
    (out / "summary.json").write_text(json.dumps(summary, indent=2))
    (out / "report.md").write_text(render_markdown(meta, metrics))
    with history.open("a") as handle:
        handle.write(history_line(meta, metrics) + "\n")
    return out
