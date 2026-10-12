"""Open and close the chat: async pool, validated semantic layer, checkpointer, models, agent.

Used by the API lifespan, `finance chat` and the integration tests.
"""

import logging
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from functools import partial

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from finance.agent.catalog import validate_layer
from finance.agent.graph import ChatModels, build_agent, chat_models
from finance.agent.semantic_layer import layer_version, load_semantic_layer
from finance.agent.service import ChatService
from finance.agent.sql_runner import run_query
from finance.agent.title import ChatTitle
from finance.agent.tools import make_run_sql
from finance.db import async_pool
from finance.settings import Settings
from finance.tracing import langfuse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def open_chat(
    settings: Settings, models: ChatModels | None = None
) -> AsyncIterator[ChatService | None]:
    """Yield the chat, or None when it is not configured (no database URL, or an xAI model
    without XAI_API_KEY): the dashboards keep working and the chat routes answer 503."""
    chat = settings.chat
    if not settings.supabase_db_url:
        logger.warning("chat disabled: SUPABASE_DB_URL is not set")
        yield None
        return
    if models is None:
        if settings.xai_api_key:
            os.environ.setdefault("XAI_API_KEY", settings.xai_api_key)
        if chat.model.startswith("xai:") and not os.environ.get("XAI_API_KEY"):
            logger.warning("chat disabled: XAI_API_KEY is not set")
            yield None
            return
        models = chat_models(chat)
    async with async_pool(timeout=chat.pool_timeout_seconds) as pool:
        layer = load_semantic_layer()
        columns = await validate_layer(pool, layer)  # fails loudly on a mismatch
        # Strict msgpack: refuse to revive unexpected types from the database (only langgraph's
        # SAFE_MSGPACK_TYPES, which include the message classes).
        checkpointer = AsyncPostgresSaver(
            pool, serde=JsonPlusSerializer(allowed_msgpack_modules=None)
        )
        await checkpointer.setup()
        run = partial(
            run_query, pool, row_limit=chat.sql_row_limit, timeout_seconds=chat.sql_timeout_seconds
        )
        tool = make_run_sql(run, rows_shown=chat.sql_rows_shown, max_chars=chat.sql_max_chars)
        try:
            yield ChatService(
                pool=pool,
                agent=build_agent(models, [tool], chat, checkpointer),
                checkpointer=checkpointer,
                layer=layer,
                columns=columns,
                layer_version=layer_version(),
                title_model=models.title.with_structured_output(ChatTitle),
                chat=chat,
            )
        finally:
            langfuse().flush()
