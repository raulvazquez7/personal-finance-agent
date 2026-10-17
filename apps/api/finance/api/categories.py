"""The taxonomy for pickers, and the check every label request goes through."""

from fastapi import APIRouter, HTTPException
from psycopg import Connection
from pydantic import BaseModel

from finance.api.deps import Db

router = APIRouter(prefix="/categories", tags=["categories"])


class CategoryOut(BaseModel):
    slug: str
    tx_type: str
    level1: str
    name: str
    group_name: str


def require_category(conn: Connection, slug: str) -> None:
    if conn.execute("select 1 from categories where slug = %s", (slug,)).fetchone() is None:
        raise HTTPException(status_code=422, detail=f"Unknown category {slug!r}")


@router.get("")
def list_categories(conn: Db) -> list[CategoryOut]:
    # A missing name reads as the slug with its first letter up ("Software ai"), as in the view.
    rows = conn.execute(
        "select c.slug, c.tx_type, c.level1,"
        " coalesce(c.name, upper(left(replace(c.slug, '_', ' '), 1))"
        "   || substr(replace(c.slug, '_', ' '), 2)) as name,"
        " coalesce(g.name, upper(left(replace(c.level1, '_', ' '), 1))"
        "   || substr(replace(c.level1, '_', ' '), 2)) as group_name"
        " from categories c left join category_groups g on g.level1 = c.level1"
        " order by c.tx_type, c.level1, c.slug"
    ).fetchall()
    return [CategoryOut.model_validate(row) for row in rows]
