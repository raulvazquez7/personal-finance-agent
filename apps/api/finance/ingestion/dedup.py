"""Deterministic transaction identity for statements that carry no transaction id."""

import hashlib
from collections import Counter

from finance.models import NormalizedTransaction


def _fingerprint(tx: NormalizedTransaction) -> tuple:
    description = " ".join(tx.description_raw.split()).upper()
    balance = "" if tx.balance_after is None else f"{tx.balance_after:.2f}"
    return (tx.booked_at.isoformat(), f"{tx.amount:.2f}", description, balance)


def occurrence_indexes(transactions: list[NormalizedTransaction]) -> list[int]:
    """Position of each row among identical rows in the same file (0, 1, 2...)."""
    seen: Counter[tuple] = Counter()
    indexes = []
    for tx in transactions:
        fingerprint = _fingerprint(tx)
        indexes.append(seen[fingerprint])
        seen[fingerprint] += 1
    return indexes


def dedup_key(iban: str, tx: NormalizedTransaction, occurrence_index: int) -> str:
    parts = (iban, *_fingerprint(tx), str(occurrence_index))
    return hashlib.sha256("|".join(parts).encode()).hexdigest()
