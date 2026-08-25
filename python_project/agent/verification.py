"""Lightweight, deterministic verification of an agent's self-reported completion
claim against what was ACTUALLY extracted/observed, instead of blindly trusting
the LLM's `finish_task(status=..., verified_count=...)` call.

This directly targets the "TASK VERIFICATION" stage from the tool-status
taxonomy: the LLM saying `status="completed"` is a CLAIM, not a fact — it must
be cross-checked against real extracted content before the run is allowed to
report COMPLETED to the user.

This is intentionally a best-effort heuristic (regex-based item counting for
"find N things" style requests), not a full semantic verifier — but it catches
the most common and highest-impact failure mode described in the spec: the
agent claiming "5 of 5 verified" when the page content it actually extracted
contains far fewer (or zero) distinct items.
"""
import re
from typing import Any, Dict, List, Optional, Tuple

# Matches phrasings like "5 latest jobs", "top 3 articles", "find 10 emails",
# "the last 24 hours" is deliberately NOT matched here (that's a time window,
# not a count) so we don't misinterpret "24" as the requested item count.
_COUNT_REQUEST_PATTERNS = [
    r'\b(\d+)\s+(?:latest|newest|recent|top|best)?\s*(?:jobs?|listings?|results?|items?|articles?|emails?|posts?|products?|links?|openings?|vacancies?)\b',
    r'\btop\s+(\d+)\b',
    r'\bfind\s+(?:the\s+)?(\d+)\b',
]

# What counts as a "distinct extracted item" in browser_extract output: a
# numbered list line, a markdown bullet, or an explicit dash-list entry.
_ITEM_LINE_PATTERN = re.compile(r'(?:^|\n)\s*(?:\d+[\.\)]|[-*•])\s+\S')


def extract_requested_count(user_prompt: str) -> Optional[int]:
    """Best-effort parse of how many discrete items the user actually asked for."""
    for pat in _COUNT_REQUEST_PATTERNS:
        m = re.search(pat, user_prompt, re.IGNORECASE)
        if m:
            try:
                val = int(m.group(1))
                if 0 < val <= 500:  # sanity bound — ignore obviously-unrelated numbers
                    return val
            except ValueError:
                continue
    return None


def count_extracted_items(
    tool_results: List[Dict[str, Any]],
    extract_tool_labels: Tuple[str, ...] = ("Browser Data Extraction",),
) -> int:
    """
    Counts distinct list-like items actually present in this run's data-extraction
    tool outputs — a concrete, checkable proxy for "how many results were really
    found", independent of whatever number the LLM later claims. Works against
    either the browser agent's `tool` key or the sandbox/general agent's
    `toolName` key.
    """
    total = 0
    for tr in tool_results:
        label = tr.get("tool") or tr.get("toolName")
        if label not in extract_tool_labels:
            continue
        data = tr.get("data") or {}
        output = tr.get("output", "") or data.get("output", "") or ""
        total += len(_ITEM_LINE_PATTERN.findall(output))
    return total


def verify_completion_claim(
    user_prompt: str,
    tool_results: List[Dict[str, Any]],
    claimed_status: str,
    claimed_verified_count: Optional[int] = None,
    claimed_requested_count: Optional[int] = None,
    extract_tool_labels: Tuple[str, ...] = (
        "Browser Data Extraction", "Sandbox File Read", "Sandbox Python Execution", "Sandbox Shell Execution",
    ),
) -> Tuple[str, Optional[int], Optional[int], Optional[str]]:
    """
    Cross-checks a self-reported finish_task/finish_sandbox_task verdict against
    what was actually extracted, instead of trusting it unconditionally.

    Returns (adjusted_status, adjusted_verified_count, adjusted_requested_count, note).
    `note` is None when no adjustment was necessary; otherwise it's a short,
    honest explanation appended to the final user-facing message.
    """
    requested = claimed_requested_count or extract_requested_count(user_prompt)
    if not requested:
        # No checkable count was ever asked for — nothing to verify against.
        return claimed_status, claimed_verified_count, claimed_requested_count, None

    actual_extracted = count_extracted_items(tool_results, extract_tool_labels)

    if actual_extracted == 0:
        if claimed_status == "completed":
            return (
                "partial", 0, requested,
                f"Downgraded from 'completed' to 'partial': the request asked for {requested} item(s), "
                "but no matching items were actually found in the extracted page content."
            )
        return claimed_status, claimed_verified_count, requested, None

    if claimed_status == "completed" and actual_extracted < requested:
        return (
            "partial", actual_extracted, requested,
            f"Downgraded from 'completed' to 'partial': only {actual_extracted} of {requested} requested "
            "item(s) were actually present in the extracted page content."
        )

    if claimed_verified_count is not None and claimed_verified_count > actual_extracted:
        return (
            claimed_status, actual_extracted, requested,
            f"Adjusted verified count from {claimed_verified_count} to {actual_extracted} based on the "
            "actual extracted content (the agent's self-reported count could not be confirmed)."
        )

    return claimed_status, (claimed_verified_count if claimed_verified_count is not None else actual_extracted), requested, None
