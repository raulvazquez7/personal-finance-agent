"""Routes for the chat (spec section 9): threads, history, feedback and the streamed answer in
the AI SDK UI message protocol."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, StringConstraints

from finance.agent import store
from finance.agent.models import ChatMessage, Feedback, Thread
from finance.agent.service import ChatService, ThreadBusy
from finance.agent.ui_stream import UI_STREAM_HEADERS, sse
from finance.tracing import langfuse

router = APIRouter(prefix="/chat", tags=["chat"])

BUSY = "This chat is still answering. Wait for it or stop it first."


def get_chat(request: Request) -> ChatService:
    chat = getattr(request.app.state, "chat", None)
    if chat is None:
        raise HTTPException(
            status_code=503,
            detail="The chat is not configured: set SUPABASE_DB_URL and XAI_API_KEY in .env",
        )
    return chat


Chat = Annotated[ChatService, Depends(get_chat)]


async def _thread(chat: ChatService, thread_id: UUID) -> Thread:
    thread = await store.get_thread(chat.pool, thread_id)
    if thread is None:
        raise HTTPException(status_code=404, detail=f"chat {thread_id} not found")
    return thread


@router.post("/threads", status_code=201)
async def create_thread(chat: Chat) -> Thread:
    return await store.create_thread(chat.pool)


@router.get("/threads")
async def list_threads(chat: Chat) -> list[Thread]:
    return await store.list_threads(chat.pool)


class RenameThread(BaseModel):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


@router.patch("/threads/{thread_id}")
async def rename_thread(thread_id: UUID, body: RenameThread, chat: Chat) -> Thread:
    thread = await store.rename_thread(chat.pool, thread_id, body.title)
    if thread is None:
        raise HTTPException(status_code=404, detail=f"chat {thread_id} not found")
    return thread


@router.delete("/threads/{thread_id}", status_code=204)
async def delete_thread(thread_id: UUID, chat: Chat) -> Response:
    try:
        deleted = await chat.delete_thread(thread_id)
    except ThreadBusy as busy:
        raise HTTPException(status_code=409, detail=BUSY) from busy
    if not deleted:
        raise HTTPException(status_code=404, detail=f"chat {thread_id} not found")
    return Response(status_code=204)


@router.get("/threads/{thread_id}/messages")
async def list_messages(thread_id: UUID, chat: Chat) -> list[ChatMessage]:
    await _thread(chat, thread_id)
    return await store.list_messages(chat.pool, thread_id)


class NewMessage(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=4000)]


@router.post("/threads/{thread_id}/messages", response_class=StreamingResponse)
async def send_message(thread_id: UUID, body: NewMessage, chat: Chat) -> StreamingResponse:
    thread = await _thread(chat, thread_id)
    try:
        parts = chat.stream_turn(thread, body.text)
    except ThreadBusy as busy:
        raise HTTPException(status_code=409, detail=BUSY) from busy
    return StreamingResponse(sse(parts), media_type="text/event-stream", headers=UI_STREAM_HEADERS)


class FeedbackBody(BaseModel):
    value: Feedback
    comment: str | None = Field(default=None, max_length=1000)


@router.post("/messages/{message_id}/feedback", status_code=204)
async def send_feedback(message_id: UUID, body: FeedbackBody, chat: Chat) -> Response:
    try:
        trace_id = await store.set_feedback(chat.pool, message_id, body.value)
    except store.MessageNotFound as missing:
        raise HTTPException(status_code=404, detail=str(missing)) from missing
    if trace_id:
        langfuse().create_score(
            trace_id=trace_id,
            score_id=f"{message_id}-feedback",  # one score per answer: a new click replaces it
            name="user-feedback",
            value=1.0 if body.value == "up" else 0.0,
            data_type="BOOLEAN",
            comment=body.comment,
        )
    return Response(status_code=204)
