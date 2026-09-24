"""Money moving between two imported accounts is internal to the household (spec 4.4)."""

import re
from datetime import date
from decimal import Decimal
from uuid import UUID, uuid4

from psycopg import Connection
from pydantic import BaseModel

from finance.settings import Settings


class PairCandidate(BaseModel):
    id: UUID
    account_id: UUID
    booked_at: date
    amount: Decimal
    description_raw: str


def find_pairs(
    rows: list[PairCandidate], pattern: str, window_days: int
) -> list[tuple[UUID, UUID]]:
    """One-to-one (outgoing, incoming) pairs, taken globally nearest booking dates first."""
    transfer = re.compile(pattern, re.IGNORECASE)
    eligible = [row for row in rows if transfer.search(row.description_raw)]
    options = [
        (abs((into.booked_at - out.booked_at).days), out, into)
        for out in eligible
        for into in eligible
        if out.amount < 0 and into.amount == -out.amount and into.account_id != out.account_id
    ]
    options.sort(key=lambda o: (o[0], o[1].booked_at, str(o[1].id), str(o[2].id)))
    used: set[UUID] = set()
    pairs = []
    for days, out, into in options:
        if days <= window_days and out.id not in used and into.id not in used:
            used.update((out.id, into.id))
            pairs.append((out.id, into.id))
    return pairs


# A row the user labelled own_accounts agrees with pairing: it pairs and keeps its label, so
# the user can mark a transfer before the other account's statement is imported.
_CANDIDATES = """
select id, account_id, booked_at, amount, description_raw from transactions
where transfer_pair_id is null and description_raw ~* %s
  and (category_source <> 'user' or category_slug = 'own_accounts')
"""

_LINK_PAIR = """
update transactions set transfer_pair_id = %(pair)s, updated_at = now() where id = any(%(ids)s)
"""

_LABEL_PAIR = """
update transactions set tx_type = 'transfer',
  category_slug = 'own_accounts', category_source = 'rule', category_confidence = 1,
  category_probabilities = null, merchant_id = null, merchant_source = 'none',
  merchant_confidence = null, is_subscription = false, subscription_score = null,
  needs_review = false, updated_at = now()
where id = any(%(ids)s) and category_source <> 'user'
returning id
"""


def pair_transfers(conn: Connection, settings: Settings) -> int:
    rows = conn.execute(_CANDIDATES, (settings.transfer_pattern,)).fetchall()
    candidates = [PairCandidate.model_validate(row) for row in rows]
    pairs = find_pairs(candidates, settings.transfer_pattern, settings.transfer_window_days)
    with conn.transaction():
        for out_id, in_id in pairs:
            params = {"pair": uuid4(), "ids": [out_id, in_id]}
            conn.execute(_LINK_PAIR, params)
            for row in conn.execute(_LABEL_PAIR, params).fetchall():
                conn.execute(
                    "insert into transaction_labels (transaction_id, category_slug, source,"
                    " confidence) values (%s, 'own_accounts', 'rule', 1)",
                    (row["id"],),
                )
    return len(pairs)
