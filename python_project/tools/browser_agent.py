"""Browser Agent Tool: Real-time web browsing, page navigation, and article/content extraction."""
import re
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional
from langchain_core.tools import tool
from tools.web_search import perform_web_search

BROWSER_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
MAX_PAGE_CHARS = 6000

def html_to_clean_markdown(html_content: str) -> str:
    """Transform raw HTML into clean, readable Markdown text."""
    # 1. Remove script, style, svg, header, footer, nav tags
    clean = re.sub(r'<(script|style|svg|noscript|header|footer|nav)[^>]*>.*?</\1>', '', html_content, flags=re.DOTALL | re.IGNORECASE)
    
    # 2. Convert common HTML tags to Markdown
    clean = re.sub(r'<h1[^>]*>(.*?)</h1>', r'\n# \1\n', clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<h2[^>]*>(.*?)</h2>', r'\n## \1\n', clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<h3[^>]*>(.*?)</h3>', r'\n### \1\n', clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<li[^>]*>(.*?)</li>', r'\n- \1', clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<p[^>]*>(.*?)</p>', r'\n\1\n', clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<br\s*/?>', '\n', clean, flags=re.IGNORECASE)
    clean = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', clean, flags=re.DOTALL | re.IGNORECASE)
    clean = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', clean, flags=re.DOTALL | re.IGNORECASE)

    # 3. Strip remaining tags
    text = re.sub(r'<[^>]+>', ' ', clean)
    
    # 4. Decode common HTML entities
    text = text.replace('&nbsp;', ' ').replace('&amp;', '&').replace('&lt;', '<').replace('&gt;', '>').replace('&quot;', '"').replace('&#39;', "'")
    
    # 5. Normalize whitespace
    lines = [line.strip() for line in text.splitlines()]
    clean_lines = [l for l in lines if l]
    return '\n\n'.join(clean_lines)[:MAX_PAGE_CHARS]

def fetch_and_read_webpage(url: str) -> Dict[str, Any]:
    """Fetch live web page from URL and extract structured metadata and clean Markdown."""
    start_time = time.time()
    
    target_url = url.strip()
    if not target_url.startswith(('http://', 'https://')):
        target_url = f"https://{target_url}"

    try:
        req = urllib.request.Request(target_url, headers={
            "User-Agent": BROWSER_USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5"
        })

        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='replace')
            status_code = response.status

            # Extract Title
            title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE | re.DOTALL)
            title = re.sub(r'<[^>]+>', '', title_match.group(1)).strip() if title_match else target_url

            # Extract Meta Description
            desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\'](.*?)["\']', html, re.IGNORECASE | re.DOTALL)
            description = desc_match.group(1).strip() if desc_match else ""

            # Extract Clean Body Content
            content = html_to_clean_markdown(html)

            duration_ms = int((time.time() - start_time) * 1000)

            formatted = (
                f"### 🌐 Browser Visited: [{title}]({target_url})\n\n"
                f"{description}\n\n"
                f"---\n\n"
                f"{content}"
            )

            return {
                "title": title,
                "url": target_url,
                "description": description,
                "content": content,
                "status": "success",
                "execution_time_ms": duration_ms,
                "formatted": formatted
            }

    except Exception as err:
        duration_ms = int((time.time() - start_time) * 1000)
        return {
            "title": f"Page: {target_url}",
            "url": target_url,
            "description": "Unable to fetch live page content.",
            "content": f"Browser navigation error: {str(err)}",
            "status": "error",
            "execution_time_ms": duration_ms,
            "formatted": f"⚠️ **Browser Navigation Error:** Could not load `{target_url}` ({str(err)})"
        }

@tool
def browse_webpage(url: str) -> str:
    """
    Navigate to any web page URL, extract its content, read articles, documentation, or specifications, and return clean Markdown.
    Args:
        url: The complete HTTP/HTTPS web address to browse (e.g. 'https://docs.python.org/3/', 'https://en.wikipedia.org/wiki/React').
    """
    res = fetch_and_read_webpage(url)
    return res["formatted"]

@tool
def search_and_browse(query: str) -> str:
    """
    Search the web for a topic and immediately navigate and read the top matching webpage to gather deep real-time information.
    Args:
        query: The search query to look up on the browser.
    """
    search_data = perform_web_search(query, max_results=3)
    results = search_data.get("results", [])

    if not results:
        return f"No search results found on the browser for: {query}"

    # Pick the top result URL and browse it
    top_url = results[0]["url"]
    page_data = fetch_and_read_webpage(top_url)

    combined = (
        f"### 🌐 Browser Search & Read: \"{query}\"\n\n"
        f"**Source Visited:** [{page_data['title']}]({top_url})\n\n"
        f"{page_data['content']}"
    )
    return combined
