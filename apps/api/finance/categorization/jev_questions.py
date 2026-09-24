"""What jev is asked (spec 5.1): code proposes the options, jev chooses."""

import re
from decimal import Decimal

from finance.categorization.taxonomy import Category, direction_of

_SPLIT = re.compile(r"[\s*/,]+|(?<=[A-Z])\.(?=[A-Z]{2})")
_HAS_DIGIT = re.compile(r"\d")
_FILLER = frozenset({"ES", "SL", "SA", "SAU", "N", "WWW", "COM", "DE", "DEL", "LA", "EL"})


def tokens_of(text: str) -> list[str]:
    """Words without punctuation, dropping reference codes (any token with a digit)."""
    words = (token.strip(".-_") for token in _SPLIT.split(text.upper()))
    return [word for word in words if word and not _HAS_DIGIT.search(word)]


def fragments(text: str, max_words: int = 4) -> list[str]:
    """Every run of 1..max_words consecutive words: the candidate names jev chooses from."""
    words = tokens_of(text)
    out: list[str] = []
    for size in range(1, max_words + 1):
        for start in range(len(words) - size + 1):
            fragment = " ".join(words[start : start + size])
            if re.search(r"[A-Z]{2}", fragment) and fragment not in out:
                out.append(fragment)
    return out


def match_key(name: str) -> str:
    """Exact-match key: MC DONALD'S == MCDONALDS."""
    return re.sub(r"[^A-Z0-9]", "", name.upper())


def significant_words(name: str) -> set[str]:
    return {word for word in tokens_of(name) if word not in _FILLER and len(word) > 2}


def jev_state(bank: str, bank_concept: str | None, merchant: str | None, amount: Decimal) -> dict:
    return {
        "bank": bank,
        "bank_concept": bank_concept,
        "merchant_text": merchant or "",
        "amount": str(amount),
        "direction": direction_of(amount),
    }


def _criterion(category: Category) -> dict:
    criterion = {"group": category.level1, "what": category.what}
    if category.not_for:
        criterion["not_for"] = category.not_for
    return criterion


def first_call_questions(leaves: list[Category], candidates: list[str]) -> dict[str, dict]:
    """One call, three independent questions (speculative fan-out)."""
    return {
        "merchant_name": {
            "type": "choice",
            "instructions": {
                "question": "Which fragment of `merchant_text` is the business or brand name,"
                " as a person would say it?",
                "not_for": "city names, country codes, branch numbers, legal suffixes like SL or"
                " SA, card numbers",
            },
            "criteria": {candidate: None for candidate in candidates}
            | {
                "none": {
                    "what": "the text names no business: a person, a generic operation (BIZUM,"
                    " TRANSFER) or a code"
                }
            },
        },
        "category": {
            "type": "choice",
            "instructions": "Which category best describes this bank transaction",
            "criteria": {category.slug: _criterion(category) for category in leaves},
        },
        "is_subscription": {
            "type": "noul",
            "instructions": {
                "question": "This is a recurring charge for a service the person can cancel",
                "examples": "streaming, software and AI tools, telecom, gym, insurance,"
                " memberships",
                "not_for": "electricity, gas or water bills, rent, mortgage, loan repayments,"
                " one-off purchases",
            },
        },
    }


def same_merchant_question(names: list[str]) -> dict[str, dict]:
    return {
        "known_merchant": {
            "type": "choice",
            "instructions": {
                "question": "Is `candidate_name` the same business as one of these known"
                " merchants? Pick it, or none",
                "inspect": ["`candidate_name`", "`merchant_text`"],
                "note": "The same business can appear with branch, city or truncation suffixes",
                "not_for": "a different business that only shares the town, the street or the"
                " kind of shop",
            },
            "criteria": {name: None for name in names}
            | {"none": {"what": "a merchant not in this list"}},
        }
    }
