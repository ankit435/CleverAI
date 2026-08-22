"""Core Types, Enums, and Dataclasses for the Browser AI Agent Platform."""
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
import time

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

class TabInfo(BaseModel):
    id: str = Field(..., description="Unique identifier for the tab")
    title: str = Field(default="Untitled", description="Current page title")
    url: str = Field(default="about:blank", description="Current tab URL")
    active: bool = Field(default=False, description="Whether this tab is currently focused/active")
    favicon: Optional[str] = Field(default=None, description="Favicon URL if available")
    window_id: Optional[str] = Field(default=None, description="Browser window identifier")

class InteractiveElement(BaseModel):
    id: int = Field(..., description="Numeric index reference for LLM reasoning (e.g., [1], [2])")
    tag: str = Field(..., description="HTML element tag (button, a, input, select, textarea)")
    role: Optional[str] = Field(default=None, description="ARIA role if applicable")
    text: str = Field(default="", description="Visible text or accessible label")
    selector: str = Field(..., description="Robust CSS or XPath selector for reliable automated interaction")
    placeholder: Optional[str] = None
    value: Optional[str] = None
    input_type: Optional[str] = None
    is_clickable: bool = True
    is_input: bool = False

class PageSnapshot(BaseModel):
    title: str
    url: str
    active_tab_id: str
    timestamp: str = Field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    elements: List[InteractiveElement] = Field(default_factory=list)
    visible_text: str = Field(default="", description="Sanitized, token-optimized visible page text")
    formatted_snapshot: str = Field(default="", description="LLM-ready structured snapshot representation")

class BrowserStatus(BaseModel):
    connected: bool
    mode: BrowserMode
    endpoint: Optional[str] = None
    browser_type: str = "chromium"
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

class ActionResult(BaseModel):
    action: str
    status: str  # "success", "error", "confirmation_required", "timeout"
    duration_ms: int = 0
    message: str = ""
    current_url: Optional[str] = None
    current_title: Optional[str] = None
    snapshot: Optional[PageSnapshot] = None
    confirmation: Optional[ConfirmationRequest] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
