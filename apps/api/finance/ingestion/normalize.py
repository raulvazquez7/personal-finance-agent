"""Parsing helpers for Spanish bank statements."""

import re
from datetime import date
from decimal import Decimal

_AMOUNT_JUNK = re.compile(r"[€\s]")
_REFERENCE_PREFIX = re.compile(r"^[\dN][\d\-]{5,}\s*")
_MULTISPACE = re.compile(r"\s+")


def parse_amount_es(text: str) -> Decimal:
    """'1.756,67' -> Decimal('1756.67'); '+2326,31€' -> Decimal('2326.31')."""
    cleaned = _AMOUNT_JUNK.sub("", text).replace(".", "").replace(",", ".")
    return Decimal(cleaned)


def parse_date_es(text: str, year: int | None = None) -> date:
    """'05/08/2026' -> date(2026, 8, 5); '05/08' needs an explicit year."""
    parts = [int(part) for part in text.split("/")]
    if len(parts) == 2:
        if year is None:
            raise ValueError(f"year is required to parse {text!r}")
        parts.append(year)
    day, month, full_year = parts
    return date(full_year, month, day)


def normalize_merchant(text: str) -> str | None:
    """Drop leading reference numbers, collapse spaces, upper-case; None when nothing is left."""
    without_reference = _REFERENCE_PREFIX.sub("", text)
    cleaned = _MULTISPACE.sub(" ", without_reference).strip(" -")
    return cleaned.upper() or None
