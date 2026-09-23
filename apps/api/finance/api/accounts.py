"""Routes for listing and renaming accounts."""

from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from finance.api.deps import Db

router = APIRouter(prefix="/accounts", tags=["accounts"])

_SELECT = "select id, bank, right(iban, 4) as iban_last4, name, currency from accounts"


class Account(BaseModel):
    id: UUID
    bank: str
    iban_last4: str
    name: str
    currency: str


class AccountUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=80)


@router.get("")
def list_accounts(conn: Db) -> list[Account]:
    rows = conn.execute(f"{_SELECT} order by created_at").fetchall()
    return [Account.model_validate(row) for row in rows]


@router.patch("/{account_id}")
def rename_account(account_id: UUID, body: AccountUpdate, conn: Db) -> Account:
    conn.execute("update accounts set name = %s where id = %s", (body.name, account_id))
    row = conn.execute(f"{_SELECT} where id = %s", (account_id,)).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Account not found")
    return Account.model_validate(row)
