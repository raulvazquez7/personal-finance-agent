"""Load what needs a category, run the categorizer, save results and label history."""

import asyncio
import logging
import threading
from collections import Counter
from uuid import UUID

from psycopg import Connection
from psycopg.types.json import Jsonb
from pydantic import BaseModel

from finance.categorization.categorizer import CategorizationContext, categorize
from finance.categorization.jev_client import Jev, TypesafeJev
from finance.categorization.jev_questions import match_key
from finance.categorization.merchants import MerchantRef, MerchantRoster
from finance.categorization.models import Categorization, TxInput
from finance.categorization.pairing import pair_transfers
from finance.categorization.rules import load_rules
from finance.categorization.taxonomy import load_taxonomy
from finance.db import connection
from finance.settings import Settings, get_settings
from finance.tracing import langfuse

logger = logging.getLogger(__name__)

# Each upload schedules a background run: one at a time, or they would ask jev twice about the
# same rows and race to create the same merchants (spec 5.1). One process only.
_run_lock = threading.Lock()

_PENDING = """
select t.id, a.bank, t.booked_at, t.amount, t.description_raw, t.bank_concept, t.merchant,
       t.transfer_pair_id
from transactions t join accounts a on a.id = t.account_id
where t.category_source = 'none' or (%(all)s and t.category_source <> 'user')
order by t.booked_at, t.id
"""

_UPDATE = """
update transactions set tx_type = %(tx_type)s, category_slug = %(category_slug)s,
  category_source = %(category_source)s, category_confidence = %(category_confidence)s,
  category_probabilities = %(category_probabilities)s, merchant_id = %(merchant_id)s,
  merchant_source = %(merchant_source)s, merchant_confidence = %(merchant_confidence)s,
  is_subscription = %(is_subscription)s, subscription_score = %(subscription_score)s,
  needs_review = %(needs_review)s, updated_at = now()
where id = %(id)s and category_source <> 'user'
"""

_LABEL = """
insert into transaction_labels (transaction_id, merchant_id, category_slug, is_subscription,
                                source, confidence, model)
values (%s, %s, %s, %s, %s, %s, %s)
"""


class CategorizeSummary(BaseModel):
    paired: int = 0
    categorized: int = 0
    needs_review: int = 0
    by_source: dict[str, int] = {}
    failed: int = 0  # pending rows jev could not answer; they stay pending for the next run
    skipped: str | None = None

    def line(self) -> str:
        if self.skipped:
            return f"categorization skipped: {self.skipped} (paired={self.paired})"
        parts = [f"paired={self.paired}", f"categorized={self.categorized}"]
        parts += [f"{source}={n}" for source, n in sorted(self.by_source.items())]
        parts.append(f"needs_review={self.needs_review}")
        if self.failed:
            parts.append(f"failed={self.failed}")
        return " ".join(parts)


def load_pending(conn: Connection, include_all: bool) -> list[TxInput]:
    rows = conn.execute(_PENDING, {"all": include_all}).fetchall()
    return [TxInput.model_validate(row) for row in rows]


def load_roster(conn: Connection) -> MerchantRoster:
    rows = conn.execute("select id, name, category_slug, is_subscription from merchants").fetchall()
    return MerchantRoster([MerchantRef.model_validate(row) for row in rows])


def _merchant_ids(conn: Connection, roster: MerchantRoster) -> dict[str, UUID]:
    ids = {m.name: m.id for m in roster.all() if m.id}
    for merchant in roster.new_merchants():
        ids[merchant.name] = conn.execute(
            "insert into merchants (name, match_key) values (%s, %s)"
            " on conflict (match_key) do update set match_key = excluded.match_key returning id",
            (merchant.name, match_key(merchant.name)),
        ).fetchone()["id"]
    return ids


def save(conn: Connection, results: list[Categorization], roster: MerchantRoster) -> None:
    with conn.transaction():
        ids = _merchant_ids(conn, roster)
        for r in results:
            merchant_id = ids.get(r.merchant_name) if r.merchant_name else None
            params = r.model_dump(
                include={
                    "tx_type",
                    "category_slug",
                    "category_source",
                    "category_confidence",
                    "merchant_source",
                    "merchant_confidence",
                    "is_subscription",
                    "subscription_score",
                    "needs_review",
                }
            )
            params |= {
                "id": r.transaction_id,
                "merchant_id": merchant_id,
                "category_probabilities": Jsonb(r.category_probabilities)
                if r.category_probabilities
                else None,
            }
            if not conn.execute(_UPDATE, params).rowcount:
                continue  # the user labelled it while jev was answering: their label stands
            if r.merge_candidate_name and merchant_id:
                conn.execute(
                    "update merchants set merge_candidate_id = %s, merge_confidence = %s"
                    " where id = %s and not confirmed",
                    (ids[r.merge_candidate_name], r.merge_confidence, merchant_id),
                )
            conn.execute(
                _LABEL,
                (
                    r.transaction_id,
                    merchant_id,
                    r.category_slug,
                    r.is_subscription,
                    r.category_source,
                    r.category_confidence,
                    r.model,
                ),
            )


async def categorize_pending(
    conn: Connection, settings: Settings, include_all: bool = False, jev: Jev | None = None
) -> CategorizeSummary:
    paired = pair_transfers(conn, settings)
    rows = load_pending(conn, include_all)
    if not rows:
        return CategorizeSummary(paired=paired)
    if jev is None and not settings.typesafe_api_key:
        return CategorizeSummary(paired=paired, skipped="TYPESAFE_API_KEY is not set")
    ctx = CategorizationContext(load_taxonomy(conn), load_rules(conn), settings)
    roster = load_roster(conn)
    # One trace per run: every jev generation nests under this span.
    with langfuse().start_as_current_observation(as_type="span", name="categorize") as span:
        if jev is None:
            async with TypesafeJev(
                settings.typesafe_api_key, concurrency=settings.jev_concurrency
            ) as client:
                results = await categorize(rows, ctx, client, roster)
        else:
            results = await categorize(rows, ctx, jev, roster)
        summary = CategorizeSummary(
            paired=paired,
            categorized=len(results),
            needs_review=sum(r.needs_review for r in results),
            by_source=dict(Counter(r.category_source for r in results)),
            failed=len(rows) - len(results),
        )
        span.update(output=summary.model_dump())
    save(conn, results, roster)
    return summary


def run_categorization(include_all: bool = False) -> CategorizeSummary:
    with connection() as conn:
        return asyncio.run(categorize_pending(conn, get_settings(), include_all))


def run_categorization_logged(include_all: bool = False) -> None:
    """Background-task entry point: an import must never fail because of categorization.

    FastAPI runs this sync function in its threadpool, so the event loop of asyncio.run and
    the blocking Langfuse flush stay off the API's own loop.
    """
    with _run_lock:
        try:
            summary = run_categorization(include_all)
        except Exception:
            logger.exception("categorization failed")
            return
        # A skipped run (no jev key) is a warning, so the API console shows it.
        logger.log(logging.WARNING if summary.skipped else logging.INFO, summary.line())
