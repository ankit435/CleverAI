"""Intent Engine: Structured natural-language task parsing into TaskIntent schema."""
import re
from typing import Any, Dict, List, Optional
from browser.schema import TaskIntent

class IntentEngine:
    """Parses user prompts into structured multi-constraint TaskIntent without hardcoded website rules."""

    @staticmethod
    def parse_intent(user_prompt: str) -> TaskIntent:
        """Parse natural-language instruction into structured TaskIntent."""
        lower = user_prompt.lower().strip()

        # 1. Detect browser requirement
        non_browser_patterns = [
            r'^(what is|explain|define|tell me about|how to|write code|give me python|who is|solve|calculate)\b'
        ]
        is_conceptual = any(re.search(p, lower) for p in non_browser_patterns) and not any(
            w in lower for w in ["open", "browse", "visit", "website", "search", "tab", "page", "click", "buy", "cart", "login", "gmail", "github", "account"]
        )

        browser_required = not is_conceptual

        # 2. Detect authentication requirement
        auth_keywords = ["my email", "my emails", "gmail", "unread", "my account", "my profile", "my orders", "my messages", "dashboard", "logged in", "inbox", "notifications"]
        auth_required = any(k in lower for k in auth_keywords)

        # 3. Extract domain / website if explicitly specified in text
        domain_match = re.search(r'\b(?:on|in|from|at|visit|open)\s+([a-zA-Z0-9_\-\.]+)\b', user_prompt, re.IGNORECASE)
        website_domain = domain_match.group(1).lower() if domain_match else None

        # 4. Extract constraints (e.g. price <= 80000, timeframe, etc.)
        constraints: Dict[str, Any] = {}
        price_match = re.search(r'(?:under|below|less than|within|above|greater than|upper than|upper)\s*(?:₹|rs\.?|inr|\$)?\s*([0-9]+k|[0-9,]+)', lower)
        if price_match:
            constraints["price_limit"] = price_match.group(0)

        # 5. Extract entities & query
        cleaned_query = re.sub(r'\b(find|search for|search|show me|look for|list all|give me|all|every)\b', '', user_prompt, flags=re.IGNORECASE).strip()

        return TaskIntent(
            goal=f"Execute: {user_prompt.strip()}",
            intent="information_retrieval_and_interaction" if browser_required else "reasoning",
            entities=[w for w in cleaned_query.split() if len(w) > 3],
            website_domain=website_domain,
            query=cleaned_query,
            constraints=constraints,
            required_actions=["observe", "search_or_navigate", "extract", "verify"],
            completion_criteria="Task completed when matching results are extracted and verified.",
            authentication_required=auth_required,
            browser_required=browser_required
        )

intent_engine = IntentEngine()
