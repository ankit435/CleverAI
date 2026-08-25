"""Short-TTL in-memory cache for tool-call results, keyed by a normalized
(tool_name, args) signature. Avoids redundant re-fetching when an agent calls
the same web_search/browser_extract/etc. with identical arguments multiple
times within a short window (e.g. the LLM re-verifying, or a supervisor +
worker both querying the same thing) — a real cost/latency win with no
behavior change for genuinely new queries.

Intentionally process-local and lightweight (no Redis/external cache): this
is a best-effort optimization, not a correctness-critical store, so an
in-memory dict with TTL eviction is sufficient and keeps zero new infra.
"""
import hashlib
import json
import threading
import time
from typing import Any, Callable, Dict, Optional, Tuple

_DEFAULT_TTL_SECONDS = 120
_MAX_ENTRIES = 500

_lock = threading.Lock()
_cache: Dict[str, Tuple[float, Any]] = {}


def _make_key(tool_name: str, args: Dict[str, Any]) -> str:
    try:
        normalized = json.dumps(args, sort_keys=True, default=str)
    except Exception:
        normalized = str(args)
    digest = hashlib.sha256(f"{tool_name}:{normalized.lower()}".encode("utf-8")).hexdigest()
    return digest


def get_cached(tool_name: str, args: Dict[str, Any]) -> Optional[Any]:
    """Returns the cached result for this tool call, or None if absent/expired."""
    key = _make_key(tool_name, args)
    with _lock:
        entry = _cache.get(key)
        if not entry:
            return None
        expires_at, value = entry
        if time.time() > expires_at:
            _cache.pop(key, None)
            return None
        return value


def set_cached(tool_name: str, args: Dict[str, Any], value: Any, ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> None:
    """Stores a tool call result with a TTL, evicting the oldest entry if over capacity."""
    key = _make_key(tool_name, args)
    with _lock:
        if len(_cache) >= _MAX_ENTRIES and key not in _cache:
            oldest_key = min(_cache, key=lambda k: _cache[k][0])
            _cache.pop(oldest_key, None)
        _cache[key] = (time.time() + ttl_seconds, value)


def cached_call(tool_name: str, args: Dict[str, Any], fn: Callable[[], Any], ttl_seconds: int = _DEFAULT_TTL_SECONDS) -> Tuple[Any, bool]:
    """
    Runs `fn()` unless a fresh cached result already exists for (tool_name, args).
    Returns (result, was_cache_hit).
    """
    cached = get_cached(tool_name, args)
    if cached is not None:
        return cached, True
    result = fn()
    set_cached(tool_name, args, result, ttl_seconds)
    return result, False


def clear_cache() -> None:
    """Clears all cached entries (used in tests)."""
    with _lock:
        _cache.clear()
