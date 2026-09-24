"""jev System One behind a small protocol, so the categorizer can run with a fake in tests."""

import asyncio
from typing import Any, Protocol

from langfuse import propagate_attributes
from pydantic import BaseModel
from typesafe_sdk import AsyncTypeSafeClient, Choice, Noul, TypeSafeError

from finance.tracing import langfuse


class JevAnswer(BaseModel):
    choice: str | None = None
    confidence: float | None = None
    probabilities: dict[str, float] = {}
    noul: float | None = None


class JevResult(BaseModel):
    answers: dict[str, JevAnswer]
    model: str
    request_id: str | None = None
    input_tokens: int = 0


class Jev(Protocol):
    async def ask(self, name: str, state: dict, questions: dict[str, dict]) -> JevResult: ...


def to_sdk(questions: dict[str, dict]) -> dict[str, Choice | Noul]:
    built: dict[str, Choice | Noul] = {}
    for name, spec in questions.items():
        if spec["type"] == "choice":
            built[name] = Choice(instructions=spec["instructions"], criteria=spec["criteria"])
        else:
            built[name] = Noul(instructions=spec["instructions"])
    return built


def _answer(raw: Any) -> JevAnswer:
    return JevAnswer(
        choice=getattr(raw, "choice", None),
        confidence=getattr(raw, "confidence", None),
        probabilities=dict(getattr(raw, "probabilities", None) or {}),
        noul=getattr(raw, "noul", None),
    )


def _request_id(response: Any) -> str | None:
    """The SDK raises when the response has no request-id header; the paid answer is kept."""
    try:
        return response.request_id
    except TypeSafeError:
        return None


class TypesafeJev:
    """Bounded concurrency, the SDK's default retry policy, one Langfuse generation per call.

    Each generation nests under the observation active in the caller's context (a root span
    started around a run, also inside tasks started by asyncio.gather) and is its own trace
    when none is active.
    """

    def __init__(self, api_key: str, concurrency: int = 8, tags: list[str] | None = None) -> None:
        self._client = AsyncTypeSafeClient(api_key=api_key)
        self._semaphore = asyncio.Semaphore(concurrency)
        self._tags = tags
        self.input_tokens = 0

    async def __aenter__(self) -> "TypesafeJev":
        await self._client.__aenter__()
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self._client.__aexit__(*exc_info)
        langfuse().flush()

    async def ask(self, name: str, state: dict, questions: dict[str, dict]) -> JevResult:
        async with self._semaphore:
            with (
                propagate_attributes(tags=self._tags),
                langfuse().start_as_current_observation(
                    as_type="generation", name=f"jev.{name}", input=state
                ) as observation,
            ):
                response = await self._client.system_one(state=state, questions=to_sdk(questions))
                result = JevResult(
                    answers={key: _answer(value) for key, value in response.answers.items()},
                    model=response.model,
                    request_id=_request_id(response),
                    input_tokens=response.usage.input_tokens or 0,
                )
                observation.update(
                    model=result.model,
                    output={k: a.model_dump(exclude_none=True) for k, a in result.answers.items()},
                    usage_details={"input": result.input_tokens},
                    metadata={"request_id": result.request_id},
                )
        self.input_tokens += result.input_tokens
        return result
