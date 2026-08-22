"""Browser AI Agent platform package."""
from browser.schema import (
    BrowserMode, BrowserStatus, TabInfo, PageSnapshot, InteractiveElement,
    ActionResult, ConfirmationRequest, RiskLevel, TaskRequirement,
    PolicyStrategy, PolicyDecision
)
from browser.policy import browser_policy, BrowserPolicyManager
from browser.session_manager import browser_session_manager, BrowserSessionManager, UserBrowserSession
from browser.security_manager import security_manager, BrowserSecurityManager
from browser.snapshot import snapshot_parser, SnapshotParser
from browser.connection_manager import BrowserConnectionManager
from browser.tab_manager import TabManager
from browser.page_controller import PageController
from browser.service import browser_service, BrowserService
from browser.tools import ALL_BROWSER_TOOLS

__all__ = [
    "BrowserMode",
    "BrowserStatus",
    "TabInfo",
    "PageSnapshot",
    "InteractiveElement",
    "ActionResult",
    "ConfirmationRequest",
    "RiskLevel",
    "TaskRequirement",
    "PolicyStrategy",
    "PolicyDecision",
    "browser_policy",
    "BrowserPolicyManager",
    "browser_session_manager",
    "BrowserSessionManager",
    "UserBrowserSession",
    "security_manager",
    "BrowserSecurityManager",
    "snapshot_parser",
    "SnapshotParser",
    "BrowserConnectionManager",
    "TabManager",
    "PageController",
    "browser_service",
    "BrowserService",
    "ALL_BROWSER_TOOLS"
]
