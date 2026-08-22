"""Core Types, Enums, and Dataclasses for the Generic Autonomous Browser Agent Platform."""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import time
import uuid

class BrowserMode(str, Enum):
    EXISTING_CDP = "existing_cdp"
    EXISTING_EXTENSION = "existing_extension"
    MANAGED_BROWSER = "managed_browser"
    REMOTE_BROWSER = "remote_browser"

class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class TaskRequirement(str, Enum):
    NO_BROWSER = "no_browser"
    PUBLIC_BROWSER = "public_browser"
    AUTHENTICATED_BROWSER = "authenticated_browser"

class PolicyStrategy(str, Enum):
    NO_ACTION = "no_action"
    USE_EXISTING = "use_existing"
    LAUNCH_MANAGED = "launch_managed"
    PROMPT_USER_TO_CONNECT = "prompt_user_to_connect"

class PageState(str, Enum):
    VALID = "VALID"
    LOADING = "LOADING"
    NOT_FOUND = "NOT_FOUND"
    ACCESS_DENIED = "ACCESS_DENIED"
    LOGIN_REQUIRED = "LOGIN_REQUIRED"
    CAPTCHA = "CAPTCHA"
    ERROR = "ERROR"
    EMPTY = "EMPTY"
    UNKNOWN = "UNKNOWN"

class ResolutionStrategy(str, Enum):
    SNAPSHOT_ID = "snapshot_id"
    ACCESSIBILITY = "accessibility"
    STABLE_ATTRIBUTES = "stable_attributes"
    VISIBLE_TEXT = "visible_text"
    DOM_HIERARCHY = "dom_hierarchy"
    SEMANTIC_RELATIONSHIP = "semantic_relationship"
    VISUAL_ANALYSIS = "visual_analysis"
    COORDINATES = "coordinates"

class VerificationType(str, Enum):
    VERIFIED = "VERIFIED"
    NOT_VERIFIED = "NOT_VERIFIED"
    UNEXPECTED = "UNEXPECTED"

class TargetConfidence(BaseModel):
    target: str
    method: ResolutionStrategy
    confidence: float = 1.0  # 0.0 to 1.0

class TaskIntent(BaseModel):
    goal: str
    intent: str
    entities: List[str] = Field(default_factory=list)
    website_domain: Optional[str] = None
    query: Optional[str] = None
    constraints: Dict[str, Any] = Field(default_factory=dict)
    required_actions: List[str] = Field(default_factory=list)
    completion_criteria: str = ""
    authentication_required: bool = False
    browser_required: bool = True

class PolicyDecision(BaseModel):
    needs_browser: bool
    task_requirement: TaskRequirement
    requires_auth: bool
    strategy: PolicyStrategy
    reason: str
    target_url: Optional[str] = None
    action_suggestion: Optional[str] = None

class TabInfo(BaseModel):
    id: str = Field(..., description="Unique identifier for the tab")
    title: str = Field(default="Untitled", description="Current page title")
    url: str = Field(default="about:blank", description="Current tab URL")
    active: bool = Field(default=False, description="Whether this tab is currently focused/active")
    favicon: Optional[str] = Field(default=None, description="Favicon URL if available")
    window_id: Optional[str] = Field(default=None, description="Browser window identifier")

class BoundingBox(BaseModel):
    x: float = 0.0
    y: float = 0.0
    width: float = 0.0
    height: float = 0.0

class InteractiveElement(BaseModel):
    id: int = Field(..., description="Numeric index reference for LLM reasoning (e.g. 1, 2)")
    element_id: str = Field(default="", description="Alphanumeric element identifier (e.g. e1, e2)")
    tag: str = Field(..., description="HTML element tag (button, a, input, select, textarea)")
    role: Optional[str] = Field(default=None, description="Computed ARIA role (e.g. button, link, textbox)")
    name: Optional[str] = Field(default="", description="Accessible name or label")
    text: str = Field(default="", description="Visible text or accessible label")
    href: Optional[str] = Field(default=None, description="Hyperlink target URL if applicable")
    aria_attributes: Dict[str, Any] = Field(default_factory=dict, description="ARIA attributes on the element")
    stable_attributes: Dict[str, Any] = Field(default_factory=dict, description="Stable identifiers (data-testid, name, id)")
    visible: bool = Field(default=True, description="Whether the element is currently visible in the DOM")
    enabled: bool = Field(default=True, description="Whether the element is interactive and not disabled")
    bounding_box: Optional[BoundingBox] = Field(default=None, description="Rendered bounding box on the screen")
    parent_context: Optional[str] = Field(default=None, description="Parent container description or landmark role")
    selector: str = Field(..., description="Robust CSS or XPath selector")
    placeholder: Optional[str] = None
    value: Optional[str] = None
    input_type: Optional[str] = None
    is_clickable: bool = True
    is_input: bool = False

class PageSnapshot(BaseModel):
    snapshot_id: str = Field(default_factory=lambda: f"snap_{str(uuid.uuid4())[:8]}")
    title: str
    url: str
    active_tab_id: str
    page_state: PageState = PageState.VALID
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    elements: List[InteractiveElement] = Field(default_factory=list)
    visible_text: str = Field(default="", description="Sanitized, token-optimized visible page text")
    formatted_snapshot: str = Field(default="", description="LLM-ready structured snapshot representation")

class BrowserStatus(BaseModel):
    connected: bool = False
    mode: BrowserMode = BrowserMode.EXISTING_CDP
    endpoint: Optional[str] = None
    cdp_endpoint: Optional[str] = None
    browser_type: Optional[str] = "Chromium"
    version: Optional[str] = None
    tabs_count: int = 0
    active_tab: Optional[TabInfo] = None
    tabs: List[TabInfo] = Field(default_factory=list)
    user_id: Optional[int] = None
    session_id: Optional[str] = None
    error: Optional[str] = None

class ConfirmationRequest(BaseModel):
    id: str
    user_id: int
    session_id: str
    action: str
    target: str
    params: Dict[str, Any] = Field(default_factory=dict)
    reason: str
    risk_level: RiskLevel = RiskLevel.HIGH
    status: str = "pending"  # "pending", "approved", "rejected", "expired"
    created_at: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    expires_at: str

class VerificationResult(BaseModel):
    action: str
    expected_result: str
    actual_result: str
    passed: bool
    verification_type: VerificationType = VerificationType.VERIFIED
    details: str = ""

class ActionResult(BaseModel):
    success: bool = True
    action: str
    target: Optional[str] = None
    status: str = "success"  # "success", "error", "confirmation_required", "timeout"
    duration_ms: int = 0
    message: str = ""
    current_url: Optional[str] = None
    current_title: Optional[str] = None
    before_state: Optional[str] = None
    after_state: Optional[str] = None
    state_changed: bool = False
    snapshot: Optional[PageSnapshot] = None
    confirmation: Optional[ConfirmationRequest] = None
    verification: Optional[VerificationResult] = None
    resolution_confidence: Optional[TargetConfidence] = None
    resolution_method: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class TaskState(BaseModel):
    goal: str
    current_page: str = "about:blank"
    current_tab: str = "tab_1"
    current_state: PageState = PageState.VALID
    completed_steps: List[str] = Field(default_factory=list)
    pending_steps: List[str] = Field(default_factory=list)
    expected_state: Optional[str] = None
    last_action: Optional[str] = None
    last_result: Optional[ActionResult] = None
    retry_count: int = 0
    max_retries: int = 3
    completion_status: str = "IN_PROGRESS"  # "IN_PROGRESS", "COMPLETED", "FAILED", "BLOCKED"
    page_number: int = 1
    has_more_pages: bool = False
    collected_items: List[Dict[str, Any]] = Field(default_factory=list)

class GoalTrackingState(BaseModel):
    user_goal: str
    current_state: str = "INITIAL"
    completed_subgoals: List[str] = Field(default_factory=list)
    next_action: Optional[str] = None
    expected_state: Optional[str] = None
    actual_state: Optional[str] = None
    is_complete: bool = False
    page_number: int = 1
    has_more_pages: bool = False
    collected_items: List[Dict[str, Any]] = Field(default_factory=list)
