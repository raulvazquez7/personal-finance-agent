"""Pydantic models the chat shares with the API: query results, threads and messages."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel


class QueryResult(BaseModel):
    """One `run_sql` call: what the UI shows, what Langfuse records, what chat_messages keeps."""

    sql: str
    columns: list[str] = []
    rows: list[list[str | None]] = []
    row_count: int = 0
    truncated: bool = False
    duration_ms: int = 0
    error: str | None = None
    hint: str | None = None
    infra_error: bool = False


TitleSource = Literal["model", "fallback", "user"]


class Thread(BaseModel):
    id: UUID
    title: str | None
    title_source: TitleSource | None
    created_at: datetime
    updated_at: datetime


MessageStatus = Literal["ok", "error", "stopped"]
Feedback = Literal["up", "down"]


class ChatMessage(BaseModel):
    id: UUID
    thread_id: UUID
    role: Literal["user", "assistant"]
    content: str
    queries: list[QueryResult]
    status: MessageStatus
    feedback: Feedback | None
    created_at: datetime
