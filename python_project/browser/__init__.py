"""Browser AI Agent platform package."""
from browser.schema import (
    BrowserMode, BrowserStatus, TabInfo, PageSnapshot, InteractiveElement,
    ActionResult, ConfirmationRequest, RiskLevel, TaskRequirement,
    PolicyStrategy, PolicyDecision, PageState, TaskIntent, TaskState, TargetConfidence
)
from browser.policy import browser_policy, BrowserPolicyManager
from browser.session_manager import browser_session_manager, BrowserSessionManager, UserBrowserSession
from browser.security_manager import security_manager, BrowserSecurityManager
from browser.snapshot import snapshot_parser, SnapshotParser
from browser.connection_manager import BrowserConnectionManager
from browser.tab_manager import TabManager
from browser.page_controller import PageController
from browser.service import browser_service, BrowserService
from browser.page_state_classifier import page_state_classifier, PageStateClassifier
from browser.page_observer import page_observer, PageObserver
from browser.action_executor import action_executor, ActionExecutor
from browser.recovery_engine import recovery_engine, RecoveryEngine
from browser.intent_engine import intent_engine, IntentEngine
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
    "PageState",
    "TaskIntent",
    "TaskState",
    "TargetConfidence",
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
    "page_state_classifier",
    "PageStateClassifier",
    "page_observer",
    "PageObserver",
    "action_executor",
    "ActionExecutor",
    "recovery_engine",
    "RecoveryEngine",
    "intent_engine",
    "IntentEngine",
    "ALL_BROWSER_TOOLS"
]
