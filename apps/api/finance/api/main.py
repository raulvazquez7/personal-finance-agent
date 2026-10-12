from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from finance.agent.runtime import open_chat
from finance.api import (
    accounts,
    categories,
    categorize,
    chat,
    dashboard,
    imports,
    merchants,
    review,
    spending,
    transactions,
)
from finance.api.deps import same_origin
from finance.settings import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open the chat (pool, checkpointer, validated semantic layer) for the app's lifetime."""
    async with open_chat(get_settings()) as chat_service:
        app.state.chat = chat_service
        yield


app = FastAPI(
    title="personal-finance-agent API",
    version="0.1.0",
    dependencies=[Depends(same_origin)],
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
# A DNS-rebinding page reaches the API under its own host name: refuse any other Host.
app.add_middleware(TrustedHostMiddleware, allowed_hosts=get_settings().trusted_hosts)
app.include_router(accounts.router)
app.include_router(categories.router)
app.include_router(categorize.router)
app.include_router(chat.router)
app.include_router(dashboard.router)
app.include_router(imports.router)
app.include_router(merchants.router)
app.include_router(review.router)
app.include_router(spending.router)
app.include_router(transactions.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
