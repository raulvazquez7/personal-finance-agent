"""Subscriptions, and what the active ones cost per month and per year (spec 6)."""

from decimal import Decimal

from psycopg import Connection

from finance.dashboard.models import SubscriptionOut, Subscriptions, SubscriptionsSummary


def active_subscriptions(conn: Connection) -> Subscriptions:
    rows = conn.execute(
        "select merchant_id, merchant_name, cadence, cadence_source, latest_amount,"
        " monthly_equivalent, last_charge, charges, active from v_subscriptions"
        " order by monthly_equivalent desc, merchant_name"
    ).fetchall()
    items = [SubscriptionOut.model_validate(row) for row in rows if row["active"]]
    ended = [SubscriptionOut.model_validate(row) for row in rows if not row["active"]]
    monthly = sum((item.monthly_equivalent for item in items), Decimal(0))
    return Subscriptions(items=items, ended=ended, monthly_total=monthly, yearly_total=monthly * 12)


def summary(subscriptions: Subscriptions) -> SubscriptionsSummary:
    return SubscriptionsSummary(
        count=len(subscriptions.items),
        monthly_total=subscriptions.monthly_total,
        yearly_total=subscriptions.yearly_total,
    )
