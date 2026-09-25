"""What a user label does (spec 5.3): one transaction, or a whole merchant as its default."""

from uuid import UUID

from psycopg import Connection

from finance.categorization.jev_questions import match_key


class NotFound(LookupError):
    pass


class DirectionMismatch(ValueError):
    """Money going out cannot be income (spec 7.3). Money in may take an expense category:
    that is a refund."""


# Taxonomy.tx_type_of in SQL: the category decides the row type (spec 2.1).
_TX_TYPE = "c.tx_type"
# Only money going out is a subscription: never a refund, never a transfer (spec 6).
_SUBSCRIPTION = f"%(sub)s and {_TX_TYPE} = 'expense' and t.amount < 0"

_LABEL_ONE = f"""
update transactions t set category_slug = c.slug, category_source = 'user',
  category_confidence = null, tx_type = {_TX_TYPE}, is_subscription = {_SUBSCRIPTION},
  merchant_id = coalesce(%(merchant)s, t.merchant_id),
  merchant_source = case when %(merchant)s::uuid is null then t.merchant_source else 'user' end,
  needs_review = false, updated_at = now()
from categories c
where c.slug = %(slug)s and t.id = %(id)s
returning t.merchant_id, t.is_subscription
"""

_RELABEL_MERCHANT = f"""
update transactions t set category_slug = c.slug, category_source = 'merchant',
  category_confidence = null, tx_type = {_TX_TYPE}, is_subscription = {_SUBSCRIPTION},
  needs_review = false, updated_at = now()
from categories c
where c.slug = %(slug)s and t.merchant_id = %(merchant)s
  and t.category_source in ('jev', 'merchant', 'none')
  -- Money going out is never income (spec 7.3): a confirm leaves those rows as they are.
  and not (t.amount < 0 and c.tx_type = 'income')
returning t.id, t.is_subscription
"""

_UNPAIR = """
update transactions set transfer_pair_id = null, needs_review = true, updated_at = now()
where transfer_pair_id = (select transfer_pair_id from transactions where id = %(id)s)
"""

_USER_LABEL = """
insert into transaction_labels (transaction_id, merchant_id, category_slug, is_subscription, source)
values (%s, %s, %s, %s, 'user')
"""


def _key_of(name: str) -> str:
    """merchants.match_key is unique: an empty key would land on another merchant's row."""
    key = match_key(name)
    if not key:
        raise ValueError(f"merchant name {name!r} has no letter A-Z or digit")
    return key


def get_or_create_merchant(conn: Connection, name: str) -> UUID:
    return conn.execute(
        "insert into merchants (name, match_key) values (%s, %s)"
        " on conflict (match_key) do update set match_key = excluded.match_key returning id",
        (name.strip(), _key_of(name)),
    ).fetchone()["id"]


def label_transaction(
    conn: Connection,
    transaction_id: UUID,
    category_slug: str,
    is_subscription: bool,
    merchant_id: UUID | None = None,
    new_merchant_name: str | None = None,
) -> None:
    with conn.transaction():
        if new_merchant_name:
            merchant_id = get_or_create_merchant(conn, new_merchant_name)
        elif merchant_id is not None:
            # A merchant merged away while the review page was open: 404, not a foreign-key error.
            known = conn.execute("select 1 from merchants where id = %s", (merchant_id,))
            if known.fetchone() is None:
                raise NotFound(f"merchant {merchant_id}")
        params = {
            "slug": category_slug,
            "sub": is_subscription,
            "merchant": merchant_id,
            "id": transaction_id,
        }
        kind = conn.execute(
            "select t.amount, t.transfer_pair_id, c.tx_type from transactions t, categories c"
            " where t.id = %s and c.slug = %s",
            (transaction_id, category_slug),
        ).fetchone()
        if kind and kind["amount"] < 0 and kind["tx_type"] == "income":
            raise DirectionMismatch(f"{category_slug} is income; this transaction is money out")
        if kind and kind["transfer_pair_id"] and category_slug != "own_accounts":
            # Not a transfer after all: both sides unpair and the other goes to review (M13).
            conn.execute(_UNPAIR, {"id": transaction_id})
        row = conn.execute(_LABEL_ONE, params).fetchone()
        if row is None:
            raise NotFound(f"transaction {transaction_id} or category {category_slug}")
        conn.execute(
            _USER_LABEL, (transaction_id, row["merchant_id"], category_slug, row["is_subscription"])
        )


def merge_merchants(conn: Connection, source_id: UUID, into_id: UUID) -> None:
    ids = {"src": source_id, "into": into_id}
    with conn.transaction():
        found = conn.execute(
            "select count(*) as n from merchants where id = any(%s)", ([source_id, into_id],)
        ).fetchone()["n"]
        if source_id == into_id or found != 2:
            raise NotFound(f"merchants {source_id} and {into_id}")
        conn.execute(
            "update transactions set merchant_id = %(into)s where merchant_id = %(src)s", ids
        )
        conn.execute(
            "update transaction_labels set merchant_id = %(into)s where merchant_id = %(src)s", ids
        )
        conn.execute(
            "update merchants set merge_candidate_id = null, merge_confidence = null"
            " where merge_candidate_id = %(src)s",
            ids,
        )
        conn.execute(
            "update merchants i set category_slug = coalesce(i.category_slug, s.category_slug),"
            " is_subscription = coalesce(i.is_subscription, s.is_subscription), confirmed = true"
            " from merchants s where i.id = %(into)s and s.id = %(src)s",
            ids,
        )
        conn.execute("delete from merchants where id = %(src)s", ids)


def confirm_merchant(
    conn: Connection,
    merchant_id: UUID,
    category_slug: str,
    is_subscription: bool,
    name: str | None = None,
    merge_into_id: UUID | None = None,
) -> UUID:
    with conn.transaction():
        if name and merge_into_id is None:
            key = _key_of(name)
            other = conn.execute(
                "select id from merchants where match_key = %s and id <> %s", (key, merchant_id)
            ).fetchone()
            if other:
                merge_into_id = other["id"]
            else:
                conn.execute(
                    "update merchants set name = %s, match_key = %s where id = %s",
                    (name.strip(), key, merchant_id),
                )
        if merge_into_id is not None:
            merge_merchants(conn, merchant_id, merge_into_id)
            merchant_id = merge_into_id
        updated = conn.execute(
            "update merchants set category_slug = %s, is_subscription = %s, confirmed = true,"
            " merge_candidate_id = null, merge_confidence = null where id = %s returning id",
            (category_slug, is_subscription, merchant_id),
        ).fetchone()
        if updated is None:
            raise NotFound(f"merchant {merchant_id}")
        params = {"slug": category_slug, "sub": is_subscription, "merchant": merchant_id}
        # The user decided for every row of the merchant: they join the golden set.
        for row in conn.execute(_RELABEL_MERCHANT, params).fetchall():
            conn.execute(
                _USER_LABEL, (row["id"], merchant_id, category_slug, row["is_subscription"])
            )
    return merchant_id


def clear_merchant_default(conn: Connection, merchant_id: UUID) -> None:
    """A mixed merchant (spec 7.3): its rows keep their labels; new rows go through jev."""
    row = conn.execute(
        "update merchants set category_slug = null, is_subscription = null where id = %s"
        " returning id",
        (merchant_id,),
    ).fetchone()
    if row is None:
        raise NotFound(f"merchant {merchant_id}")


def set_note(conn: Connection, transaction_id: UUID, note: str | None) -> None:
    """A note is not a label: no label history (spec 4)."""
    text = (note or "").strip() or None
    row = conn.execute(
        "update transactions set note = %s, updated_at = now() where id = %s returning id",
        (text, transaction_id),
    ).fetchone()
    if row is None:
        raise NotFound(f"transaction {transaction_id}")


def dismiss_merge(conn: Connection, merchant_id: UUID) -> None:
    row = conn.execute(
        "update merchants set confirmed = true, merge_candidate_id = null, merge_confidence = null"
        " where id = %s returning id",
        (merchant_id,),
    ).fetchone()
    if row is None:
        raise NotFound(f"merchant {merchant_id}")
