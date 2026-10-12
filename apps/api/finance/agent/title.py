"""A short title for a new chat, from its first question, by a model without reasoning (spec
section 8). A title is cosmetic: any failure falls back to the question itself."""

import logging

from langchain_core.runnables import Runnable, RunnableConfig
from pydantic import BaseModel, Field

from finance.agent.models import TitleSource

logger = logging.getLogger(__name__)

TITLE_INSTRUCTIONS = (
    "You name chats about personal finances. Return a title of 3 to 6 words for a chat that "
    "starts with the user's message, in the language of that message, without quotes or a "
    "final period."
)


class ChatTitle(BaseModel):
    """A short title for a chat."""

    title: str = Field(
        description="3 to 6 words in the language of the question, no quotes, no final period"
    )


def fallback_title(question: str, max_chars: int) -> str:
    text = " ".join(question.split())
    return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…"


async def generate_title(
    model: Runnable, question: str, max_chars: int, config: RunnableConfig | None = None
) -> tuple[str, TitleSource]:
    """`model` returns a ChatTitle (a chat model's with_structured_output(ChatTitle))."""
    try:
        answer = await model.ainvoke(
            [("system", TITLE_INSTRUCTIONS), ("user", question)], config=config
        )
        title = " ".join(answer.title.strip().strip("\"'“”«»").rstrip(".").split())
        if 0 < len(title) <= max_chars:
            return title, "model"
        logger.warning("chat title of %d characters ignored", len(title))
    except Exception:
        logger.warning("chat title generation failed", exc_info=True)
    return fallback_title(question, max_chars), "fallback"
