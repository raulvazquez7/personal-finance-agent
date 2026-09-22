"""Domain models shared by ingestion, API and CLI."""

from datetime import date
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Bank = Literal["bbva", "caixabank"]


class StatementHeader(BaseModel):
    bank: Bank
    iban: str = Field(pattern=r"^[A-Z]{2}\d{2}[A-Z0-9]{11,30}$", description="IBAN without spaces")
    period_start: date | None = None
    period_end: date | None = None


class NormalizedTransaction(BaseModel):
    booked_at: date
    value_date: date | None = None
    amount: Decimal = Field(description="Signed: negative for money out")
    currency: str = "EUR"
    description_raw: str = Field(min_length=1)
    merchant: str | None = None
    balance_after: Decimal | None = None


class ParsedStatement(BaseModel):
    header: StatementHeader
    transactions: list[NormalizedTransaction]


class ImportSummary(BaseModel):
    import_id: UUID
    account_id: UUID
    bank: Bank
    iban_last4: str
    filename: str
    rows_total: int
    rows_new: int
    rows_duplicate: int
