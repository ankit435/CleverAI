"""Multi-Agent Supervisor: routes each user request to the specialist worker agent
best suited to own it (Browser Agent, Sandbox Agent, or the General multi-tool agent).

This is a lightweight, deterministic-first router (regex/policy based, no extra LLM
round-trip) so routing itself never adds latency or cost. Whichever agent is chosen
still retains full on-demand access to the *other* specialists mid-run via the
handoff tools in `agent.handoff` — routing only decides who starts the task, not who
is allowed to help finish it.
"""
import re
from enum import Enum
from typing import List, Optional

from browser.schema import PolicyDecision, PolicyStrategy
from browser.service import browser_service


class AgentRoute(str, Enum):
    BROWSER = "browser_agent"
    SANDBOX = "sandbox_agent"
    GENERAL = "general_agent"


# Explicit code/command execution intent — routes straight to the Sandbox Agent
# instead of the general multi-tool loop, so it gets a dedicated iterative
# execute -> observe -> retry loop rather than a single one-shot tool call.
SANDBOX_INTENT_PATTERNS = [
    r"\brun\s+(?:this\s+)?(?:the\s+)?(?:code|script|command|program|python|shell|bash)\b",
    r"\bexecute\s+(?:this\s+)?(?:the\s+)?(?:code|script|command|program|python|shell|bash)\b",
    r"\binstall\s+(?:the\s+)?(?:package|library|dependency|dependencies|pip|npm)\b",
    r"\bopen\s+(?:a\s+)?terminal\b",
    r"\bshell\s+command\b",
    r"\bbash\s+command\b",
    r"\bwrite\s+(?:a\s+)?(?:script|program)\s+(?:and\s+run|that\s+runs|to\s+run)\b",
    r"\brun\s+it\s+(?:locally|for\s+me)\b",
]


def _detect_sandbox_intent(user_prompt: str) -> bool:
    lower = user_prompt.lower()
    return any(re.search(pattern, lower) for pattern in SANDBOX_INTENT_PATTERNS)


def _sandbox_agent_enabled(active_plugin_ids: List[str]) -> bool:
    return "sandbox-agent" in active_plugin_ids or "sandbox_agent" in active_plugin_ids


def decide_route(
    user_prompt: str,
    active_plugin_ids: Optional[List[str]] = None,
    user_id: int = 1,
) -> AgentRoute:
    """
    Determine which specialist worker agent should own this request end-to-end.

    Precedence:
      1. Explicit sandbox/code-execution intent (only if the user enabled the
         Sandbox Agent plugin — it is opt-in due to its unrestricted local
         execution mode).
      2. Browser navigation/authenticated-account intent.
      3. General multi-tool agent (research, calculator, image generation,
         document Q&A, dynamic tool building).
    """
    plugins = active_plugin_ids or []

    if _sandbox_agent_enabled(plugins) and _detect_sandbox_intent(user_prompt):
        return AgentRoute.SANDBOX

    policy: PolicyDecision = browser_service.evaluate_intent(user_prompt, user_id=user_id)
    if policy.needs_browser and policy.strategy in (
        PolicyStrategy.USE_EXISTING,
        PolicyStrategy.LAUNCH_MANAGED,
        PolicyStrategy.PROMPT_USER_TO_CONNECT,
    ):
        return AgentRoute.BROWSER

    return AgentRoute.GENERAL
