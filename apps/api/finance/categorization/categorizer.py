"""The cascade without the database: pairing, system rules, jev, merchant defaults, gate."""

import asyncio
import logging
from dataclasses import dataclass
from uuid import UUID

from finance.categorization.jev_client import Jev, JevResult
from finance.categorization.jev_questions import first_call_questions, fragments, jev_state
from finance.categorization.merchants import MerchantResolution, MerchantRoster, resolve_merchant
from finance.categorization.models import Categorization, TxInput
from finance.categorization.rules import Rule, is_refund, match_rule
from finance.categorization.taxonomy import Category, Taxonomy, direction_of
from finance.settings import Settings

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CategorizationContext:
    taxonomy: Taxonomy
    rules: list[Rule]
    settings: Settings


def category_options(tx: TxInput, ctx: CategorizationContext) -> list[Category]:
    """The options jev picks from: the row's direction, except that a card purchase coming
    back is a refund and takes an expense category (spec 2.2)."""
    direction = direction_of(tx.amount)
    if direction == "incoming" and is_refund(
        ctx.rules, tx.bank, tx.bank_concept, tx.merchant, direction
    ):
        return ctx.taxonomy.leaves("outgoing")
    return ctx.taxonomy.leaves(direction)


def from_rule(tx: TxInput, slug: str, taxonomy: Taxonomy) -> Categorization:
    return Categorization(
        transaction_id=tx.id,
        tx_type=taxonomy.tx_type_of(slug, tx.amount),
        category_slug=slug,
        category_source="rule",
        category_confidence=1.0,
        level1_confidence=1.0,
        transfer_pair_id=tx.transfer_pair_id,
    )


def decide(
    tx: TxInput,
    first: JevResult,
    resolution: MerchantResolution,
    ctx: CategorizationContext,
    use_merchant_defaults: bool,
) -> Categorization:
    taxonomy, settings = ctx.taxonomy, ctx.settings
    category = first.answers["category"]
    slug, confidence, source = category.choice, category.confidence, "jev"
    level1_confidence = taxonomy.level1_sums(category.probabilities).get(taxonomy.get(slug).level1)
    score = first.answers["is_subscription"].noul
    is_subscription = (score or 0) > settings.subscription_threshold
    merchant = resolution.merchant
    if use_merchant_defaults and merchant:
        # A default applies in both directions: a shop's refunds take its category (spec 2.2).
        # Money going out is never income (spec 7.3), so an income default skips it.
        default = merchant.category_slug
        if default and not (tx.amount < 0 and taxonomy.get(default).tx_type == "income"):
            slug, source = default, "merchant"
            confidence = level1_confidence = None
        if merchant.is_subscription is not None:
            is_subscription = merchant.is_subscription
    tx_type = taxonomy.tx_type_of(slug, tx.amount)
    # Only money going out is a subscription: never a refund, never a transfer (spec 6).
    is_subscription = is_subscription and tx_type == "expense" and tx.amount < 0
    below_threshold = source == "jev" and confidence < settings.category_threshold
    return Categorization(
        transaction_id=tx.id,
        tx_type=tx_type,
        category_slug=slug,
        category_source=source,
        category_confidence=confidence,
        level1_confidence=level1_confidence,
        category_probabilities=category.probabilities,
        merchant_name=merchant.name if merchant else None,
        merchant_source="jev" if merchant else "none",
        merchant_confidence=resolution.confidence if merchant else None,
        merge_candidate_name=resolution.merge_candidate.name
        if resolution.merge_candidate
        else None,
        merge_confidence=resolution.merge_confidence,
        is_subscription=is_subscription,
        subscription_score=score,
        needs_review=below_threshold or resolution.dropped,
        model=first.model,
    )


async def categorize(
    rows: list[TxInput],
    ctx: CategorizationContext,
    jev: Jev | None,
    roster: MerchantRoster,
    *,
    use_merchant_defaults: bool = True,
) -> list[Categorization]:
    """Results in the order of `rows`. A row whose jev call fails (after the SDK's retries) or
    whose answer cannot be used is left out and logged, so one bad row never costs the others;
    it stays pending for the next run. Pairing and rule rows never call jev and always come
    back. With `jev=None` only pairing and rule rows come back: a rules-only run."""
    results: dict[UUID, Categorization] = {}
    pending: list[TxInput] = []
    for tx in rows:
        if tx.transfer_pair_id:
            results[tx.id] = from_rule(tx, "own_accounts", ctx.taxonomy)
        elif rule := match_rule(
            ctx.rules, tx.bank, tx.bank_concept, tx.merchant, direction_of(tx.amount)
        ):
            results[tx.id] = from_rule(tx, rule.category_slug, ctx.taxonomy)
        else:
            pending.append(tx)
    if jev is None:
        return [results[tx.id] for tx in rows if tx.id in results]

    states = [jev_state(tx.bank, tx.bank_concept, tx.merchant, tx.amount) for tx in pending]
    firsts = await asyncio.gather(
        *(
            jev.ask(
                "categorize",
                state,
                first_call_questions(category_options(tx, ctx), fragments(tx.merchant or "")),
            )
            for tx, state in zip(pending, states, strict=True)
        ),
        return_exceptions=True,
    )
    # Merchants are resolved one at a time in booking order, so each is created once.
    ordered = sorted(
        zip(pending, states, firsts, strict=True),
        key=lambda item: (item[0].booked_at, str(item[0].id)),
    )
    for tx, state, first in ordered:
        try:
            if isinstance(first, BaseException):
                raise first  # the first call failed; a cancellation is not caught below
            resolution = await resolve_merchant(
                first.answers["merchant_name"], state, roster, jev, ctx.settings
            )
            # A malformed answer (a slug outside the taxonomy, no confidence) fails this row only.
            results[tx.id] = decide(tx, first, resolution, ctx, use_merchant_defaults)
        except Exception as error:
            # The id and the error only: never the jev state or the description text.
            logger.warning("jev failed for transaction %s: %r", tx.id, error)
    return [results[tx.id] for tx in rows if tx.id in results]
