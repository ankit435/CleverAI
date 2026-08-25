"""Lightweight persistent long-term memory store, keyed by user_id, backed by a
local SQLite file (no external DB/infra required — the Python agent service is
self-contained). This complements `memory/manager.py`'s SessionMemoryManager
(which only holds short-term, in-process, per-thread chat history that is lost
on restart): this store survives restarts and is shared across all threads for
the same user, for durable facts/preferences ("I prefer remote jobs in Bangalore",
"my resume is at ...", "default currency is INR") that should carry across
conversations.

Design goals:
- Zero new infra: plain sqlite3, one small table.
- Bounded: capped facts per user to avoid unbounded growth from a chatty agent.
- Explicit, not automatic inference: facts are stored only when the agent (or a
  future UI action) explicitly calls `remember_fact` — we do NOT silently mine
  every message for "facts", which would be unpredictable and privacy-risky.
"""
import os
import sqlite3
import threading
import time
from typing import Dict, List, Optional

_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "user_memory.sqlite3")
_DB_PATH = os.path.normpath(_DB_PATH)
_MAX_FACTS_PER_USER = 50

_lock = threading.Lock()


def _get_conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(_DB_PATH), exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, timeout=5)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_facts (
            user_id INTEGER NOT NULL,
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            updated_at REAL NOT NULL,
            PRIMARY KEY (user_id, key)
        )
        """
    )
    return conn


def remember_fact(user_id: int, key: str, value: str) -> None:
    """Stores/updates a single durable fact for a user (e.g. key='job_preference')."""
    key = (key or "").strip().lower()[:64]
    value = (value or "").strip()[:500]
    if not key or not value:
        return
    with _lock:
        conn = _get_conn()
        try:
            conn.execute(
                "INSERT INTO user_facts (user_id, key, value, updated_at) VALUES (?, ?, ?, ?) "
                "ON CONFLICT(user_id, key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
                (user_id, key, value, time.time()),
            )
            # Enforce a per-user cap by evicting the oldest fact beyond the limit.
            count = conn.execute("SELECT COUNT(*) FROM user_facts WHERE user_id=?", (user_id,)).fetchone()[0]
            if count > _MAX_FACTS_PER_USER:
                conn.execute(
                    "DELETE FROM user_facts WHERE user_id=? AND key IN ("
                    "  SELECT key FROM user_facts WHERE user_id=? ORDER BY updated_at ASC LIMIT ?"
                    ")",
                    (user_id, user_id, count - _MAX_FACTS_PER_USER),
                )
            conn.commit()
        finally:
            conn.close()


def forget_fact(user_id: int, key: str) -> None:
    key = (key or "").strip().lower()[:64]
    if not key:
        return
    with _lock:
        conn = _get_conn()
        try:
            conn.execute("DELETE FROM user_facts WHERE user_id=? AND key=?", (user_id, key))
            conn.commit()
        finally:
            conn.close()


def get_facts(user_id: int) -> Dict[str, str]:
    """Returns all remembered facts for a user as a flat key->value dict."""
    with _lock:
        conn = _get_conn()
        try:
            rows = conn.execute(
                "SELECT key, value FROM user_facts WHERE user_id=? ORDER BY updated_at DESC", (user_id,)
            ).fetchall()
            return {k: v for k, v in rows}
        finally:
            conn.close()


def get_facts_as_context(user_id: int) -> str:
    """Formats a user's remembered facts into a short prompt-injectable block."""
    facts = get_facts(user_id)
    if not facts:
        return ""
    lines = [f"- {k.replace('_', ' ')}: {v}" for k, v in facts.items()]
    return "Known long-term facts/preferences about this user (from prior sessions):\n" + "\n".join(lines)
