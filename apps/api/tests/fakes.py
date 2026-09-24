"""A scripted jev for unit tests: no network, deterministic answers."""

from finance.categorization.jev_client import JevAnswer, JevResult


def _choice(probabilities: dict[str, float]) -> JevAnswer:
    choice = max(probabilities, key=probabilities.get)
    return JevAnswer(choice=choice, confidence=probabilities[choice], probabilities=probabilities)


def jev_result(
    *,
    merchant: dict[str, float] | None = None,
    category: dict[str, float] | None = None,
    subscription: float = 0.05,
    known: dict[str, float] | None = None,
) -> JevResult:
    answers = {"is_subscription": JevAnswer(noul=subscription)}
    if merchant is not None:
        answers["merchant_name"] = _choice(merchant)
    if category is not None:
        answers["category"] = _choice(category)
    if known is not None:
        answers["known_merchant"] = _choice(known)
    return JevResult(answers=answers, model="jev-test", request_id="req_test", input_tokens=100)


DEFAULT_RESULT = jev_result(
    merchant={"none": 1.0},
    category={"uncategorized_expense": 0.3, "other_income": 0.3, "own_accounts": 0.4},
)


class FakeJev:
    """First-call answers keyed by merchant_text, same-merchant answers by candidate_name."""

    def __init__(self, first=None, same=None, default=DEFAULT_RESULT) -> None:
        self.first = first or {}
        self.same = same or {}
        self.default = default
        self.calls: list[tuple[str, dict]] = []

    async def ask(self, name: str, state: dict, questions: dict) -> JevResult:
        self.calls.append((name, dict(state)))
        if name == "categorize":
            return self.first.get(state["merchant_text"], self.default)
        return self.same[state["candidate_name"]]
