"""Name the merchant from jev's pick: exact key, then a same-merchant question (spec 5.1)."""

from uuid import UUID

from pydantic import BaseModel

from finance.categorization.jev_client import Jev, JevAnswer
from finance.categorization.jev_questions import (
    match_key,
    same_merchant_question,
    significant_words,
    tokens_of,
)
from finance.settings import Settings


class MerchantRef(BaseModel):
    id: UUID | None = None
    name: str
    category_slug: str | None = None
    is_subscription: bool | None = None


class MerchantRoster:
    """Known merchants by exact key. New ones are added in booking order, one at a time."""

    def __init__(self, merchants: list[MerchantRef]) -> None:
        self._by_key = {match_key(m.name): m for m in merchants}
        self._new: list[MerchantRef] = []

    def get(self, name: str) -> MerchantRef | None:
        return self._by_key.get(match_key(name))

    def shortlist(self, name: str) -> list[MerchantRef]:
        words = significant_words(name)
        return [m for m in self._by_key.values() if words & set(tokens_of(m.name))]

    def add(self, name: str) -> MerchantRef:
        merchant = MerchantRef(name=name)
        self._by_key[match_key(name)] = merchant
        self._new.append(merchant)
        return merchant

    def new_merchants(self) -> list[MerchantRef]:
        return list(self._new)

    def all(self) -> list[MerchantRef]:
        return list(self._by_key.values())


class MerchantResolution(BaseModel):
    merchant: MerchantRef | None = None
    confidence: float | None = None
    merge_candidate: MerchantRef | None = None
    merge_confidence: float | None = None
    dropped: bool = False


def brand_confidence(answer: JevAnswer) -> float:
    """Nested fragments (ACME, ACME FOODS) are all right: their probabilities add up."""
    chosen = answer.choice or "none"
    if chosen == "none":
        return 0.0
    return sum(
        p for f, p in answer.probabilities.items() if f != "none" and (f in chosen or chosen in f)
    )


async def resolve_merchant(
    answer: JevAnswer, state: dict, roster: MerchantRoster, jev: Jev, settings: Settings
) -> MerchantResolution:
    chosen = answer.choice
    if chosen in (None, "none"):
        return MerchantResolution()
    brand = brand_confidence(answer)
    if brand < settings.brand_threshold:
        return MerchantResolution(confidence=brand, dropped=True)
    if known := roster.get(chosen):
        return MerchantResolution(merchant=known, confidence=brand)
    shortlist = roster.shortlist(chosen)
    if shortlist:
        result = await jev.ask(
            "same_merchant",
            {**state, "candidate_name": chosen},
            same_merchant_question([m.name for m in shortlist]),
        )
        same = result.answers["known_merchant"]
        match = next((m for m in shortlist if m.name == same.choice), None)
        if match and same.confidence >= settings.merge_threshold:
            return MerchantResolution(merchant=match, confidence=same.confidence)
        if match and same.confidence >= settings.merge_suggestion_floor:
            return MerchantResolution(
                merchant=roster.add(chosen),
                confidence=brand,
                merge_candidate=match,
                merge_confidence=same.confidence,
            )
    return MerchantResolution(merchant=roster.add(chosen), confidence=brand)
