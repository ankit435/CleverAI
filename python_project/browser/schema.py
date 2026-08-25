"""Core types for the Stagehand-backed Browser Agent platform.

Deliberately smaller than the previous in-house implementation: Stagehand's own
`act`/`observe`/`extract` primitives absorb most of what used to require bespoke
element/selector/snapshot modeling (`InteractiveElement`, `TargetConfidence`,
`ResolutionStrategy`, etc. are gone because Stagehand's AI resolves targets
internally). What remains models: connection status, tabs, one generic action
result envelope, and the human-confirmation security gate — the pieces that are
genuinely specific to *this* platform rather than to Stagehand itself.
"""
import time
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BrowserMode(str, Enum):
    """How the underlying Chromium instance is obtained."""
    EXISTING_CDP = "existing_cdp"       # Attach to the user's already-running Chrome/Edge.
    MANAGED_BROWSER = "managed_browser"  # Stagehand launches + owns a fresh local Chromium.


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class PolicyStrategy(str, Enum):
    NO_ACTION = "no_action"
    USE_EXISTING = "use_existing"
    LAUNCH_MANAGED = "launch_managed"
    PROMPT_USER_TO_CONNECT = "prompt_user_to_connect"


class TaskRequirement(str, Enum):
    NO_BROWSER = "no_browser"
    PUBLIC_BROWSER = "public_browser"
    AUTHENTICATED_BROWSER = "authenticated_browser"


class PolicyDecision(BaseModel):
    needs_browser: bool
    task_requirement: TaskRequirement
    requires_auth: bool
    strategy: PolicyStrategy
    reason: str


class TabInfo(BaseModel):
    id: str = Field(..., description="Stagehand page_id for this tab")
    title: str = Field(default="Untitled")
    url: str = Field(default="about:blank")
    active: bool = Field(default=False)


class BrowserStatus(BaseModel):
    connected: bool = False
    mode: BrowserMode = BrowserMode.EXISTING_CDP
    cdp_endpoint: Optional[str] = None
    browser_type: str = "Chromium (Stagehand)"
    tabs_count: int = 0
    active_tab: Optional[TabInfo] = None
    tabs: List[TabInfo] = Field(default_factory=list)
    user_id: Optional[int] = None
    error: Optional[str] = None


class ConfirmationRequest(BaseModel):
    id: str
    user_id: int
    instruction: str
    reason: str
    risk_level: RiskLevel = RiskLevel.HIGH
    status: str = "pending"  # pending | approved | rejected | expired
    created_at: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    expires_at: str


class ActionResult(BaseModel):
    """
    Generic envelope for every Browser Agent operation (act/observe/extract/navigate).

    `status` is deliberately granular and MUST NOT be collapsed to a plain
    success/error boolean by any caller:
      - "success"               execution completed; check `data`/message for results
      - "no_results"             execution completed; page had nothing matching
      - "error"                  execution failed (non-timeout, non-availability issue)
      - "timeout"                execution exceeded its time budget (tool IS available)
      - "unavailable"            the browser capability itself cannot be used right now
      - "auth_required"          the site/action needs the user to log in first
      - "confirmation_required"  a risky action is paused pending human approval
    """
    success: bool = True
    action: str
    status: str = "success"
    duration_ms: int = 0
    message: str = ""
    current_url: Optional[str] = None
    current_title: Optional[str] = None
    confirmation: Optional[ConfirmationRequest] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    # Real sub-span latency breakdown (item 3): instead of one opaque
    # `duration_ms` hiding session acquisition/navigation/DOM work/Stagehand
    # reasoning behind a single number, this maps stage name -> milliseconds
    # spent, e.g. {"session_acquisition_ms": 12, "stagehand_call_ms": 4200}.
    timing_breakdown: Optional[Dict[str, int]] = None


CONFIRMATION_EXPIRY_SECONDS = 300
