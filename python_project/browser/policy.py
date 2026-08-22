"""Browser Policy Engine: Determines whether a request requires browser, checks auth needs, and selects connection strategy."""
import re
from typing import List, Optional, Tuple
from browser.schema import TaskRequirement, PolicyStrategy, PolicyDecision, BrowserStatus

# Keywords indicating private user authenticated account actions
AUTHENTICATED_DOMAINS_AND_KEYWORDS = [
    r'\b(?:my\s+)?gmail\b',
    r'\b(?:my\s+)?unread\s+emails?\b',
    r'\b(?:my\s+)?inbox\b',
    r'\b(?:my\s+)?private\s+repo(?:sitory)?\b',
    r'\b(?:my\s+)?github\s+(?:notifications?|pull\s*requests?|issues?)\b',
    r'\b(?:my\s+)?linkedin\s+(?:messages?|notifications?|profile|feed)\b',
    r'\b(?:my\s+)?facebook\s+messages?\b',
    r'\b(?:my\s+)?twitter\s+dms?\b',
    r'\b(?:my\s+)?bank(?:ing)?\s+(?:account|balance|statement)\b',
    r'\b(?:my\s+)?dashboard\b',
    r'\b(?:my\s+)?cart\b',
    r'\b(?:my\s+)?orders?\b',
    r'\b(?:my\s+)?account\s+settings?\b',
    r'\bcheck\s+my\s+email\b',
    r'\bread\s+my\s+email\b',
    r'\bsend\s+an?\s+email\b'
]

# Keywords indicating public web exploration where a browser should navigate / search
PUBLIC_WEB_INTENTS = [
    r'\bsearch\s+(?:the\s+web|online|google|bing|duckduckgo)\b',
    r'\bfind\s+(?:flights?|hotels?|tickets?|prices?|deals?|jobs?)\b',
    r'\bsearch\s+amazon\b',
    r'\bsearch\s+(?:github|linkedin|naukri|indeed|wikipedia|youtube|twitter|reddit)\b',
    r'\bopen\s+(?:[a-zA-Z0-9_\-\.\:\/]+)', # Matches "open youtube", "open google", "open github", "open tab"
    r'\bgo\s+to\s+(?:[a-zA-Z0-9_\-\.\:\/]+)', # Matches "go to youtube", "go to amazon"
    r'\bvisit\s+(?:[a-zA-Z0-9_\-\.\:\/]+)', # Matches "visit youtube", "visit google"
    r'\bplay\s+.*(?:youtube|video|song|music)',
    r'\bbrowse\s+(?:[a-zA-Z0-9_\-\.\:\/]+)',
    r'\bwhat\s+(?:is|are)\s+the\s+latest\s+news\b',
    r'\blatest\s+documentation\b'
]

class BrowserPolicyManager:
    """Evaluates task intent and determines the optimal browser strategy."""

    @staticmethod
    def evaluate_request(user_prompt: str, browser_status: Optional[BrowserStatus] = None) -> PolicyDecision:
        """
        Autonomously determine if request needs browser, whether it requires user auth,
        and the recommended connection strategy.
        """
        text = user_prompt.strip()
        lower = text.lower()
        is_connected = bool(browser_status and browser_status.connected)

        # 1. Check if it's an authenticated private session request
        for pattern in AUTHENTICATED_DOMAINS_AND_KEYWORDS:
            if re.search(pattern, lower, re.IGNORECASE):
                if is_connected:
                    return PolicyDecision(
                        needs_browser=True,
                        task_requirement=TaskRequirement.AUTHENTICATED_BROWSER,
                        requires_auth=True,
                        strategy=PolicyStrategy.USE_EXISTING,
                        reason="Request involves user authenticated session (e.g. Gmail/GitHub) and existing browser is connected."
                    )
                else:
                    return PolicyDecision(
                        needs_browser=True,
                        task_requirement=TaskRequirement.AUTHENTICATED_BROWSER,
                        requires_auth=True,
                        strategy=PolicyStrategy.PROMPT_USER_TO_CONNECT,
                        reason="Task requires user's authenticated session (e.g. Gmail/GitHub). Fresh browser would hit a login wall."
                    )

        # 2. Check if it's a public web browsing/search/open website task
        has_url = bool(re.search(r'https?://[^\s]+|www\.[^\s]+|[a-z0-9_\-]+\.(?:com|org|io|net|in|dev|ai)', text, re.IGNORECASE))
        is_public_browser = has_url or any(re.search(p, lower, re.IGNORECASE) for p in PUBLIC_WEB_INTENTS)

        if is_public_browser:
            if is_connected:
                return PolicyDecision(
                    needs_browser=True,
                    task_requirement=TaskRequirement.PUBLIC_BROWSER,
                    requires_auth=False,
                    strategy=PolicyStrategy.USE_EXISTING,
                    reason="Public web task will leverage existing active browser session."
                )
            else:
                return PolicyDecision(
                    needs_browser=True,
                    task_requirement=TaskRequirement.PUBLIC_BROWSER,
                    requires_auth=False,
                    strategy=PolicyStrategy.LAUNCH_MANAGED,
                    reason="Public web task. No existing browser detected; automatically launching managed Playwright Chromium."
                )

        # 3. Check for explicit tab management commands
        if any(w in lower for w in ["what tabs", "list tabs", "show tabs", "switch tab", "close tab", "browser status"]):
            if is_connected:
                return PolicyDecision(
                    needs_browser=True,
                    task_requirement=TaskRequirement.PUBLIC_BROWSER,
                    requires_auth=False,
                    strategy=PolicyStrategy.USE_EXISTING,
                    reason="Direct tab management query using connected browser."
                )
            else:
                return PolicyDecision(
                    needs_browser=True,
                    task_requirement=TaskRequirement.AUTHENTICATED_BROWSER,
                    requires_auth=True,
                    strategy=PolicyStrategy.PROMPT_USER_TO_CONNECT,
                    reason="Tab management requires connecting to user's running browser."
                )

        # 4. Default: No browser required for concepts, coding, math, general explanation
        return PolicyDecision(
            needs_browser=False,
            task_requirement=TaskRequirement.NO_BROWSER,
            requires_auth=False,
            strategy=PolicyStrategy.NO_ACTION,
            reason="Request is an informational, coding, or mathematical query that does not require web navigation."
        )

browser_policy = BrowserPolicyManager()
