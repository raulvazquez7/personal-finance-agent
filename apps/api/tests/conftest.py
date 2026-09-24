import os
from datetime import date
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest

from finance.db import connection

# The repo-root .env holds real Langfuse keys: tests export no traces, except the opt-in live
# jev test (RUN_LIVE_JEV=1). The SDK reads this variable when the client is created.
if os.environ.get("RUN_LIVE_JEV") != "1":
    os.environ["LANGFUSE_TRACING_ENABLED"] = "false"

RAW_DIR = Path(__file__).resolve().parents[3] / "data" / "raw"


@pytest.fixture
def raw_pdfs() -> list[Path]:
    """Real statements on the developer machine; skipped everywhere else."""
    pdfs = sorted(RAW_DIR.glob("*.pdf"))
    if not pdfs:
        pytest.skip("no statements in data/raw")
    return pdfs


@pytest.fixture
def db_conn():
    """A real local database connection; everything the test writes is rolled back."""
    with connection() as conn:
        with conn.transaction(force_rollback=True):
            yield conn


@pytest.fixture
def make_tx(db_conn):
    """Insert a synthetic transaction (fake IBAN) and return its id."""

    def _make(
        amount: str,
        description_raw: str,
        *,
        iban: str = "ES0000000000000000000001",
        bank: str = "bbva",
        booked_at: date = date(2026, 7, 1),
        merchant: str | None = None,
        bank_concept: str | None = None,
    ) -> UUID:
        account = db_conn.execute(
            "insert into accounts (bank, iban, name) values (%s, %s, %s)"
            " on conflict (iban) do update set name = excluded.name returning id",
            (bank, iban, f"test {iban[-4:]}"),
        ).fetchone()["id"]
        import_id = db_conn.execute(
            "insert into imports (account_id, filename, file_sha256, rows_total)"
            " values (%s, 'test.pdf', 'x', 1) returning id",
            (account,),
        ).fetchone()["id"]
        value = Decimal(amount)
        return db_conn.execute(
            "insert into transactions (account_id, import_id, booked_at, amount, description_raw,"
            " merchant, bank_concept, dedup_key, tx_type)"
            " values (%s, %s, %s, %s, %s, %s, %s, %s, %s) returning id",
            (
                account,
                import_id,
                booked_at,
                value,
                description_raw,
                merchant,
                bank_concept,
                uuid4().hex,
                "expense" if value < 0 else "income",
            ),
        ).fetchone()["id"]

    return _make
