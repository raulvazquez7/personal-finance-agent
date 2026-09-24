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


def require_category(conn: Connection, slug: str) -> None:
    if conn.execute("select 1 from categories where slug = %s", (slug,)).fetchone() is None:
        raise HTTPException(status_code=422, detail=f"Unknown category {slug!r}")


@router.get("")
def list_categories(conn: Db) -> list[CategoryOut]:
    rows = conn.execute(
        "select slug, tx_type, level1 from categories order by tx_type, level1, slug"
    ).fetchall()
    return [CategoryOut.model_validate(row) for row in rows]
