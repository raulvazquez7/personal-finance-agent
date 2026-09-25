"""The filters every dashboard read shares, as one SQL fragment over v_transactions_enriched."""

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from psycopg import Connection

from finance.dashboard.periods import Period

WHERE = """
booked_at between %(start)s and %(end)s
and (cardinality(%(accounts)s::uuid[]) = 0 or account_id = any(%(accounts)s))
and (%(tx_type)s::text is null or tx_type = %(tx_type)s)
and (%(level1)s::text is null or coalesce(level1, 'uncategorized') = %(level1)s)
and (%(category)s::text is null or coalesce(category_slug, 'uncategorized') = %(category)s)
and (%(merchant_id)s::uuid is null or merchant_id = %(merchant_id)s)
"""

_ACCOUNTS = "(cardinality(%(accounts)s::uuid[]) = 0 or account_id = any(%(accounts)s))"


@dataclass(frozen=True)
class Scope:
    accounts: tuple[UUID, ...] = ()
    tx_type: str | None = None
    level1: str | None = None
    category: str | None = None
    merchant_id: UUID | None = None

    def params(self, period: Period) -> dict:
        return {
            "start": period.start,
            "end": period.end,
            "accounts": list(self.accounts),
            "tx_type": self.tx_type,
            "level1": self.level1,
            "category": self.category,
            "merchant_id": self.merchant_id,
        }


def latest_day(conn: Connection, accounts: tuple[UUID, ...]) -> date | None:
    row = conn.execute(
        f"select max(booked_at) as day from transactions where {_ACCOUNTS}",
        {"accounts": list(accounts)},
    ).fetchone()
    return row["day"]


def data_months(conn: Connection, period: Period, accounts: tuple[UUID, ...]) -> set[str]:
    """Months with at least one imported transaction of these accounts (spec 2.6)."""
    rows = conn.execute(
        "select distinct to_char(booked_at, 'YYYY-MM') as month from transactions"
        f" where booked_at between %(start)s and %(end)s and {_ACCOUNTS}",
        {"start": period.start, "end": period.end, "accounts": list(accounts)},
    ).fetchall()
    return {row["month"] for row in rows}


def has_data(conn: Connection, period: Period, accounts: tuple[UUID, ...]) -> bool:
    return bool(data_months(conn, period, accounts))
