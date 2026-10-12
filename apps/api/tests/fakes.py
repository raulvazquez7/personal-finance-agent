"""Scripted jev and chat models for unit tests: no network, deterministic answers."""

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field

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
    """First-call answers keyed by merchant_text, same-merchant answers by candidate_name.

    A scripted exception is raised instead of answered: jev failing for that row.
    """

    def __init__(self, first=None, same=None, default=DEFAULT_RESULT) -> None:
        self.first = first or {}
        self.same = same or {}
        self.default = default
        self.calls: list[tuple[str, dict]] = []
        self.questions: list[dict] = []  # what each call asked, in the order of `calls`

    async def ask(self, name: str, state: dict, questions: dict) -> JevResult:
        self.calls.append((name, dict(state)))
        self.questions.append(questions)
        if name == "categorize":
            answer = self.first.get(state["merchant_text"], self.default)
        else:
            answer = self.same[state["candidate_name"]]
        if isinstance(answer, Exception):
            raise answer
        return answer


class ScriptedChatModel(BaseChatModel):
    """A chat model that answers from a script and records every request. create_agent binds
    tools to it; the script decides which tool calls it makes."""

    responses: list[BaseMessage]
    calls: list[list[BaseMessage]] = Field(default_factory=list)

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.calls.append(list(messages))
        return ChatResult(generations=[ChatGeneration(message=self.responses.pop(0))])

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs) -> "ScriptedChatModel":
        return self


def tool_call(sql: str, call_id: str) -> AIMessage:
    """A scripted model turn that calls run_sql once."""
    return AIMessage(
        content="", tool_calls=[{"name": "run_sql", "args": {"sql": sql}, "id": call_id}]
    )
