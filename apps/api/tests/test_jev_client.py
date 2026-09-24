import asyncio
import os
from decimal import Decimal
from types import SimpleNamespace

import pytest
from typesafe_sdk import Choice, Noul

from finance.categorization import jev_client
from finance.categorization.jev_client import TypesafeJev, _answer, to_sdk
from finance.categorization.jev_questions import (
    first_call_questions,
    jev_state,
    same_merchant_question,
)
from finance.categorization.seed import SEED_DIR
from finance.categorization.taxonomy import Taxonomy, read_categories_yaml


def test_to_sdk_builds_choice_and_noul():
    built = to_sdk(
        {
            "a": {"type": "choice", "instructions": "q", "criteria": {"x": None, "y": None}},
            "b": {"type": "noul", "instructions": "yes or no"},
        }
    )
    assert isinstance(built["a"], Choice) and isinstance(built["b"], Noul)


def test_answer_reads_choice_and_noul_shapes():
    choice = _answer(
        SimpleNamespace(choice="x", confidence=0.9, probabilities={"x": 0.9, "y": 0.1})
    )
    noul = _answer(SimpleNamespace(noul=0.2))
    assert (choice.choice, choice.confidence, choice.noul) == ("x", 0.9, None)
    assert (noul.choice, noul.noul, noul.probabilities) == (None, 0.2, {})


class StubClient:
    """Stands in for AsyncTypeSafeClient: no network, one canned answer."""

    def __init__(self) -> None:
        self.questions: list[dict] = []

    async def __aenter__(self) -> "StubClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        pass

    async def system_one(self, state: dict, questions: dict) -> SimpleNamespace:
        self.questions.append(questions)
        answer = SimpleNamespace(
            choice="ACME FOODS", confidence=0.9, probabilities={"ACME FOODS": 0.95, "none": 0.05}
        )
        return SimpleNamespace(
            answers={"known_merchant": answer},
            model="jev-stub",
            request_id="req-1",
            usage=SimpleNamespace(input_tokens=42),
        )


def test_ask_maps_the_response_and_counts_tokens(monkeypatch):
    stub = StubClient()
    monkeypatch.setattr(jev_client, "AsyncTypeSafeClient", lambda api_key: stub)
    questions = same_merchant_question(["ACME FOODS"])

    async def ask_twice():
        async with TypesafeJev("sk-fake") as jev:
            first = await jev.ask("same_merchant", {"merchant_text": "ACME FOODS"}, questions)
            await jev.ask("same_merchant", {"merchant_text": "ACME FOODS"}, questions)
            return first, jev.input_tokens

    result, total = asyncio.run(ask_twice())
    assert result.answers["known_merchant"].choice == "ACME FOODS"
    assert result.answers["known_merchant"].probabilities["none"] == 0.05
    assert (result.model, result.request_id, result.input_tokens, total) == (
        "jev-stub",
        "req-1",
        42,
        84,
    )
    assert isinstance(stub.questions[0]["known_merchant"], Choice)


@pytest.mark.integration
def test_real_jev_answers_a_synthetic_question():
    """The only live jev test: it costs money, so it runs only when asked for."""
    from finance.settings import get_settings

    if os.environ.get("RUN_LIVE_JEV") != "1":
        pytest.skip("live jev call: set RUN_LIVE_JEV=1 to run it")
    key = get_settings().typesafe_api_key or os.environ.get("TYPESAFE_API_KEY")
    if not key:
        pytest.skip("no TYPESAFE_API_KEY")
    leaves = Taxonomy(read_categories_yaml(SEED_DIR / "categories.yaml")).leaves("outgoing")

    async def ask():
        async with TypesafeJev(key, tags=["test"]) as jev:
            state = {"merchant_text": "ACME FOODS", "candidate_name": "ACME"}
            same = await jev.ask("same_merchant", state, same_merchant_question(["ACME FOODS"]))
            # No merchant text: merchant_name offers only `none` (the merchant-None case).
            card = jev_state("bbva", "PAGO CON TARJETA", None, Decimal("-12.50"))
            first = await jev.ask("categorize", card, first_call_questions(leaves, []))
            return same, first, jev.input_tokens

    same, first, total = asyncio.run(ask())
    assert same.answers["known_merchant"].choice in {"ACME FOODS", "none"}
    assert same.model.startswith("jev")
    assert first.answers["merchant_name"].choice == "none"
    assert first.answers["category"].choice in {category.slug for category in leaves}
    assert total == same.input_tokens + first.input_tokens > 0
