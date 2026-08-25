"""Tool 1: Web Search Engine for real-time live internet information retrieval."""
import re
import urllib.parse
import urllib.request
from typing import Any, Dict, List
from langchain_core.tools import tool

def decode_search_url(raw_url: str) -> str:
    """Decodes search engine tracking redirect URLs into direct destination URLs."""
    if not raw_url:
        return ""
    if "bing.com/ck/a?" in raw_url or "bing.com/ck/a!" in raw_url:
        parsed = urllib.parse.urlparse(raw_url)
        params = urllib.parse.parse_qs(parsed.query)
        if "u" in params and params["u"]:
            u_val = params["u"][0]
            if u_val.startswith("a1"):
                import base64
                try:
                    b64_str = u_val[2:]
                    padded = b64_str + '=' * (-len(b64_str) % 4)
                    decoded = base64.b64decode(padded).decode("utf-8", errors="ignore")
                    if decoded.startswith("http"):
                        return decoded
                except Exception:
                    pass
    return raw_url

def _live_html_search(query: str, max_results: int = 5) -> List[Dict[str, str]]:
    """Fetch live web search results via a plain HTTP request (no browser needed).

    Kept independent from the Browser Agent on purpose: Stagehand's act/observe/
    extract primitives are built for AI-guided page interaction, not for being a
    cheap scraping backend for every search query the General Agent makes. A
    direct HTTP fetch + regex parse of Bing's HTML is faster and doesn't consume
    a browser session at all.
    """
    try:
        enc = urllib.parse.quote_plus(query)
        req = urllib.request.Request(
            f"https://www.bing.com/search?q={enc}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8", errors="ignore")

        results: List[Dict[str, str]] = []
        for block in re.findall(r'<li class="b_algo">(.*?)</li>', html, re.DOTALL)[:max_results]:
            link_match = re.search(r'<h2><a href="([^"]+)"[^>]*>(.*?)</a></h2>', block, re.DOTALL)
            if not link_match:
                continue
            href, title_html = link_match.groups()
            title = re.sub(r'<[^>]+>', '', title_html).strip()
            snippet_match = re.search(r'<p>(.*?)</p>', block, re.DOTALL)
            snippet = re.sub(r'<[^>]+>', '', snippet_match.group(1)).strip() if snippet_match else ""
            if title and href:
                results.append({"title": title, "url": decode_search_url(href.strip()), "snippet": snippet})
        return results
    except Exception:
        return []


def perform_web_search(query: str, max_results: int = 5) -> Dict[str, Any]:
    """Execute live web search query and return parsed results with titles, snippets, and citations."""
    cleaned_query = re.sub(r'^(search for|search|find|latest|look up|google|give me the link of|give me)\s*', '', query, flags=re.IGNORECASE).strip() or query

    results = _live_html_search(cleaned_query, max_results=max_results)

    if not results:
        return {
            "query": cleaned_query,
            "results": [],
            # Explicit machine-readable status so callers never have to
            # string-match `formatted` to tell "executed successfully with
            # zero matches" apart from "the search tool itself failed".
            "status": "no_results",
            "formatted": f"No live search results could be retrieved for '{cleaned_query}'."
        }

    formatted_text = f"### Web Search Results for '{cleaned_query}':\n\n"
    for idx, r in enumerate(results, 1):
        formatted_text += f"{idx}. **[{r['title']}]({r['url']})**\n   {r['snippet']}\n\n"

    return {
        "query": cleaned_query,
        "results": results,
        "status": "results_found",
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
