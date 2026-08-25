"""Distinguishable exception types for the Browser Agent platform.

These exist so `browser/service.py` can map failures to the correct granular
`ActionResult.status` ("unavailable" vs "timeout" vs "auth_required" vs plain
"error") instead of collapsing every exception into a generic error string —
which is exactly the ambiguity that causes the agent to misreport "the tool
is unavailable" when it actually just timed out or found no results.
"""


class BrowserUnavailableError(Exception):
    """The browser capability itself cannot be initialized/used right now
    (e.g. no local Chromium binary, Stagehand failed to start, CDP endpoint
    refused connection). This is NOT a per-action failure — it means the tool
    is genuinely unavailable until the environment issue is resolved."""


class BrowserAuthRequiredError(Exception):
    """The browser is available and the operation executed, but the target
    site/action requires the user to authenticate before it can proceed."""
