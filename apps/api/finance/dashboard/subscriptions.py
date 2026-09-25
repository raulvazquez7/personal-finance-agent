"""Active subscriptions and what they cost per month and per year (spec 6)."""

from decimal import Decimal

from psycopg import Connection

from finance.dashboard.models import SubscriptionOut, Subscriptions, SubscriptionsSummary


def active_subscriptions(conn: Connection) -> Subscriptions:
    rows = conn.execute(
        "select merchant_id, merchant_name, cadence, typical_amount, monthly_equivalent,"
        " last_charge, charges from v_subscriptions where active"
        " order by monthly_equivalent desc, merchant_name"
    ).fetchall()
    items = [SubscriptionOut.model_validate(row) for row in rows]
    monthly = sum((item.monthly_equivalent for item in items), Decimal(0))
    return Subscriptions(items=items, monthly_total=monthly, yearly_total=monthly * 12)


def summary(subscriptions: Subscriptions) -> SubscriptionsSummary:
    return SubscriptionsSummary(
        count=len(subscriptions.items),
        monthly_total=subscriptions.monthly_total,
        yearly_total=subscriptions.yearly_total,
    )
