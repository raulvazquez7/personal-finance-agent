"""Split a bank line into what categorization reads; the card number stays in description_raw.

Same rules as the backfill in supabase/migrations/20260924000000_categorization.sql.
"""

import re

from pydantic import BaseModel

from finance.models import Bank

_CARD_NUMBER = re.compile(r"\b\d{12,19}\b")
_SPACES = re.compile(r"\s+")


class Structured(BaseModel):
    bank_concept: str | None
    merchant: str | None
    card_last4: str | None


def structure(bank: Bank, description_raw: str, merchant: str | None) -> Structured:
    """BBVA prints its own operation label before ' | '; CaixaBank has none."""
    concept = description_raw.split(" | ", 1)[0] if bank == "bbva" else None
    card = _CARD_NUMBER.search(description_raw)
    return Structured(
        bank_concept=_without_card_number(concept),
        merchant=_without_card_number(merchant),
        card_last4=card.group()[-4:] if card else None,
    )


def _without_card_number(text: str | None) -> str | None:
    """Text without a card number is left as is, like the backfill's `where` clause."""
    if text is None or not _CARD_NUMBER.search(text):
        return text
    return _SPACES.sub(" ", _CARD_NUMBER.sub("", text)).strip() or None


def mask_card_numbers(text: str) -> str:
    """Every card number as '•••• ' plus its last four digits, for text shown in the web app."""
    return _CARD_NUMBER.sub(lambda card: f"•••• {card.group()[-4:]}", text)
