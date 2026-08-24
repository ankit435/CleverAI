
"""Request-scoped context variables for the browser agent.

Using contextvars.ContextVar ensures each agent execution carries its own
user_id/thread_id without any thread-safety issues (works with asyncio,
threadpool executors, and sync Playwright worker threads alike).
"""
from contextvars import ContextVar
from typing import Optional

# Stores the authenticated user_id for the current agent run.
# Default is 1 (single-user / development fallback).
_current_user_id: ContextVar[int] = ContextVar("current_user_id", default=1)

# Stores the conversation/thread_id for the current agent run so the Browser
# Agent can keep one dedicated tab per conversation inside the user's single
# shared browser, instead of spawning a new browser per turn/conversation.
_current_thread_id: ContextVar[Optional[str]] = ContextVar("current_thread_id", default=None)


def set_current_user_id(user_id: int) -> None:
    """Call once at the start of each agent execution to bind the user_id."""
    _current_user_id.set(user_id)


def get_current_user_id() -> int:
    """Return the user_id bound to the current execution context."""
    return _current_user_id.get()


def set_current_thread_id(thread_id: Optional[str]) -> None:
    """Call once at the start of each agent execution to bind the conversation thread_id."""
    _current_thread_id.set(thread_id)


def get_current_thread_id() -> Optional[str]:
    """Return the conversation thread_id bound to the current execution context."""
    return _current_thread_id.get()



