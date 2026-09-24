"""The review inbox: one item per merchant, largest spend first."""

from fastapi import APIRouter
from psycopg import Connection
from pydantic import BaseModel

from finance.api.deps import Db
from finance.categorization.review_queue import (
    MergeSuggestion,
    ReviewItem,
    ReviewRow,
    build_review_items,
)
from finance.categorization.taxonomy import load_taxonomy

router = APIRouter(prefix="/review", tags=["review"])

_ROWS = """
select t.id, t.booked_at, t.amount, t.description_raw, a.name as account_name, t.merchant_id,
       m.name as merchant_name, m.category_slug as merchant_category_slug, t.category_slug,
       t.category_confidence, t.category_probabilities, t.is_subscription
from transactions t
join accounts a on a.id = t.account_id
left join merchants m on m.id = t.merchant_id
where t.category_source <> 'user'
  and (t.needs_review or (m.merge_candidate_id is not null and not m.confirmed))
order by t.booked_at, t.id
"""

_MERGES = """
select m.id, c.id as merchant_id, c.name, m.merge_confidence as confidence
from merchants m join merchants c on c.id = m.merge_candidate_id
where not m.confirmed
"""


class ReviewCount(BaseModel):
    pending: int
    uncategorized: int  # rows no run has categorized yet: no jev key, or jev failed on them


def review_items(conn: Connection) -> list[ReviewItem]:
    rows = [ReviewRow.model_validate(row) for row in conn.execute(_ROWS).fetchall()]
    merges = {row["id"]: MergeSuggestion.model_validate(row) for row in conn.execute(_MERGES)}
    return build_review_items(rows, merges, load_taxonomy(conn))


@router.get("")
def get_review(conn: Db) -> list[ReviewItem]:
    return review_items(conn)


@router.get("/count")
def get_review_count(conn: Db) -> ReviewCount:
    uncategorized = conn.execute(
        "select count(*) as n from transactions where category_source = 'none'"
    ).fetchone()["n"]
    return ReviewCount(pending=len(review_items(conn)), uncategorized=uncategorized)
