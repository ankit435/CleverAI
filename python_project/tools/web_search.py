"""Tool 1: Web Search Engine for real-time live internet information retrieval."""
import re
import urllib.parse
import urllib.request
import json
from typing import Any, Dict, List
from langchain_core.tools import tool

def _live_browser_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Fetch live web search results using browser worker."""
    try:
        from browser.service import browser_service
        def _task():
            sess = browser_service.session_manager.get_session(1)
            if not sess or not sess.context:
                browser_service.session_manager.launch_managed_browser(1)
                sess = browser_service.session_manager.get_session(1)
            if not sess or not sess.context:
                return []
            
            page = sess.tab_manager._tab_map.get("tab_1") or sess.context.new_page()
            enc = urllib.parse.quote_plus(query)
            page.goto(f"https://www.bing.com/search?q={enc}", wait_until="domcontentloaded", timeout=12000)
            
            results = []
            locators = page.locator("li.b_algo")
            count = locators.count()
            for i in range(min(count, max_results)):
                loc = locators.nth(i)
                title = loc.locator("h2 a").inner_text()
                href = loc.locator("h2 a").get_attribute("href")
                snippet = loc.locator(".b_caption p").inner_text() if loc.locator(".b_caption p").count() > 0 else ""
                if title and href:
                    results.append({"title": title.strip(), "url": href.strip(), "snippet": snippet.strip()})
            return results

        return browser_service.worker.run(_task)
    except Exception:
        return []

def perform_web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Execute live web search query and return parsed results with titles, snippets, and citations."""
    cleaned_query = re.sub(r'^(search for|search|find|latest|look up|google|give me the link of|give me)\s*', '', query, flags=re.IGNORECASE).strip() or query
    encoded = urllib.parse.quote_plus(cleaned_query)
    results: List[Dict[str, str]] = []

    # 1. Try Live Browser Search (Bing / Google)
    try:
        results = _live_browser_search(cleaned_query, max_results=max_results)
    except Exception:
        pass

    if not results:
        return {
            "query": cleaned_query,
            "results": [],
            "formatted": f"No live search results could be retrieved for '{cleaned_query}'."
        }

    formatted_text = f"### Web Search Results for '{cleaned_query}':\n\n"
    for idx, r in enumerate(results, 1):
        formatted_text += f"{idx}. **[{r['title']}]({r['url']})**\n   {r['snippet']}\n\n"

    return {
        "query": cleaned_query,
        "results": results,
        "formatted": formatted_text.strip()
    }

@tool
def web_search(query: str) -> str:
    """
    Search the web for real-time information, current news, job listings, documentation, or recent developments.
    Args:
        query: The search query terms to find online.
    """
    data = perform_web_search(query)
    return data["formatted"]
