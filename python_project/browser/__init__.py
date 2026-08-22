"""Browser AI Agent platform package."""
from browser.schema import (
    BrowserMode, BrowserStatus, TabInfo, PageSnapshot, InteractiveElement,
    ActionResult, ConfirmationRequest, RiskLevel
)
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
