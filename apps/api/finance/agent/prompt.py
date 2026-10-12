"""The agent's instructions and the system message built on every model call (spec section 7.1).

The instructions name no table or column: the data model arrives as the data context, so a change
to the views never touches this text, and a prompt change never breaks a stored thread.
"""

from hashlib import sha256
from pathlib import Path

from langchain_core.messages import SystemMessage

PROMPTS_DIR = Path(__file__).parent / "prompts"
INSTRUCTIONS = (PROMPTS_DIR / "system.md").read_text(encoding="utf-8")
SUMMARY_PROMPT = (PROMPTS_DIR / "summary.md").read_text(encoding="utf-8")
PROMPT_VERSION = sha256(INSTRUCTIONS.encode()).hexdigest()[:12]


def system_message(data_context: str) -> SystemMessage:
    """Instructions first (identical every turn, so the provider caches them), data context next."""
    return SystemMessage(
        content=[{"type": "text", "text": INSTRUCTIONS}, {"type": "text", "text": data_context}]
    )
