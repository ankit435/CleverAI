"""LangChain tool wrapper exposing the persistent user-memory store to agents,
so they can explicitly save/recall durable user facts/preferences across
sessions (e.g. "remember I prefer remote jobs in Bangalore").
"""
from typing import Optional
from langchain_core.tools import tool
from memory.persistent_store import remember_fact, forget_fact, get_facts
from browser.context import get_current_user_id


@tool
def remember_user_fact(key: str, value: str) -> str:
    """
    Saves a durable fact/preference about the current user for future conversations
    (e.g. key='preferred_job_location', value='Bangalore, remote-friendly'). Use this
    ONLY when the user explicitly states a preference/fact worth remembering long-term
    — never store credentials, tokens, or sensitive personal data.
    """
    user_id = get_current_user_id() or 1
    remember_fact(user_id, key, value)
    return f"Remembered: {key} = {value}"


@tool
def forget_user_fact(key: str) -> str:
    """Removes a previously remembered fact/preference for the current user by key."""
    user_id = get_current_user_id() or 1
    forget_fact(user_id, key)
    return f"Forgotten: {key}"


@tool
def recall_user_facts() -> str:
    """Lists all durable facts/preferences currently remembered about the current user."""
    user_id = get_current_user_id() or 1
    facts = get_facts(user_id)
    if not facts:
        return "No long-term facts are currently remembered about this user."
    return "\n".join(f"- {k}: {v}" for k, v in facts.items())
