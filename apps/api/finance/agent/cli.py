"""`finance chat`: the web chat's agent in the terminal, on the same threads."""

from collections.abc import Callable
from uuid import UUID

from finance.agent import store
from finance.agent.graph import ChatModels
from finance.agent.runtime import open_chat
from finance.settings import get_settings


def render(part: dict) -> str | None:
    """What the terminal shows for one stream part: the answer, each query and its outcome."""
    kind = part["type"]
    if kind == "text-delta":
        return part["delta"]
    if kind == "text-end":
        return "\n"
    if kind == "tool-input-available":
        return f"\n[query]\n{part['input'].get('sql', '').strip()}\n"
    if kind == "tool-output-available":
        output = part["output"]
        if output.get("error"):
            return f"[query failed] {output['error']}\n"
        return f"[{output.get('row_count', 0)} rows]\n"
    if kind == "data-title":
        return f"[title] {part['data']['title']}\n"
    if kind == "error":
        return f"[error] {part['errorText']}\n"
    return None


async def chat_session(
    questions: list[str] | Callable[[], str | None],
    thread_id: UUID | None,
    write: Callable[[str], None],
    models: ChatModels | None = None,
) -> int:
    """Answer each question (a list, or a reader that returns None to stop); 1 if the chat is
    not configured or the thread does not exist."""
    async with open_chat(get_settings(), models) as chat:
        if chat is None:
            write("The chat is not configured: set SUPABASE_DB_URL and XAI_API_KEY in .env\n")
            return 1
        thread = (
            await store.get_thread(chat.pool, thread_id)
            if thread_id
            else await store.create_thread(chat.pool)
        )
        if thread is None:
            write(f"chat {thread_id} not found\n")
            return 1
        write(f"chat {thread.id}\n")
        pending = iter(questions) if isinstance(questions, list) else iter(questions, None)
        for question in pending:
            async for part in chat.stream_turn(thread, question):
                if (text := render(part)) is not None:
                    write(text)
            thread_id = thread.id
            thread = await store.get_thread(chat.pool, thread_id)  # it may have a title now
            if thread is None:  # deleted from the web meanwhile
                write(f"chat {thread_id} not found\n")
                return 1
    return 0
