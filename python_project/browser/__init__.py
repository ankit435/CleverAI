"""Browser AI Agent platform package — powered by Stagehand (local Chromium mode)."""
from browser.schema import (
    BrowserMode, BrowserStatus, TabInfo, ActionResult, ConfirmationRequest,
    RiskLevel, TaskRequirement, PolicyStrategy, PolicyDecision,
)
from browser.policy import browser_policy, BrowserPolicyManager
from browser.security_manager import security_manager, BrowserSecurityManager
from browser.session_manager import browser_session_manager, BrowserSessionManager, UserBrowserSession
from browser.service import browser_service, BrowserService

__all__ = [
    "BrowserMode",
    "BrowserStatus",
    "TabInfo",
    "ActionResult",
    "ConfirmationRequest",
    "RiskLevel",
    "TaskRequirement",
    "PolicyStrategy",
    "PolicyDecision",
    "browser_policy",
    "BrowserPolicyManager",
    "security_manager",
    "BrowserSecurityManager",
    "browser_session_manager",
    "BrowserSessionManager",
    "UserBrowserSession",
    "browser_service",
    "BrowserService",
]
