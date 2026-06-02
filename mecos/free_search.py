"""
MECOS Free Search
=================
Pulls search results from Wikipedia and DuckDuckGo.
Zero API keys. Zero cost.

Dependencies:
    pip install requests beautifulsoup4 wikipedia-api
"""

import logging
import time
from dataclasses import dataclass

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "MECOSBot/1.0 (personal research assistant; github.com/0ssy/MECOS)"
}


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str  # "wikipedia" | "duckduckgo"


def search_wikipedia(query: str, max_results: int = 3) -> list[SearchResult]:
    """Use the Wikipedia REST API — completely free, no key."""
    results = []
    try:
        search_url = "https://en.wikipedia.org/w/api.php"
        params = {
            "action": "query",
            "list": "search",
            "srsearch": query,
            "srlimit": max_results,
            "format": "json",
        }
        response = requests.get(search_url, params=params, headers=HEADERS, timeout=10)
        response.raise_for_status()
        items = response.json().get("query", {}).get("search", [])

        for item in items:
            title = item["title"]
            summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}"
            summary_response = requests.get(summary_url, headers=HEADERS, timeout=10)
            if summary_response.ok:
                data = summary_response.json()
                snippet = data.get("extract", "")[:500]
                url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
                results.append(SearchResult(title=title, url=url, snippet=snippet, source="wikipedia"))
            time.sleep(0.3)

    except Exception as exc:
        logger.warning("Wikipedia search failed: %s", exc)

    return results


def search_duckduckgo(query: str, max_results: int = 5) -> list[SearchResult]:
    """Scrape DuckDuckGo HTML results — free, no key."""
    results = []
    try:
        url = "https://html.duckduckgo.com/html/"
        data = {"q": query, "b": ""}
        response = requests.post(url, data=data, headers=HEADERS, timeout=15)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        for result in soup.select(".result__body")[:max_results]:
            title_el = result.select_one(".result__title")
            snippet_el = result.select_one(".result__snippet")
            link_el = result.select_one(".result__url")

            title = title_el.get_text(strip=True) if title_el else ""
            snippet = snippet_el.get_text(strip=True) if snippet_el else ""
            link = link_el.get_text(strip=True) if link_el else ""
            if not link.startswith("http"):
                link = "https://" + link

            if title:
                results.append(SearchResult(title=title, url=link, snippet=snippet, source="duckduckgo"))

    except Exception as exc:
        logger.warning("DuckDuckGo search failed: %s", exc)

    return results


def free_search(query: str, max_total: int = 8) -> list[SearchResult]:
    """
    Try Wikipedia first (highest quality), then fill remaining slots
    with DuckDuckGo results. No API keys needed.
    """
    wiki_results = search_wikipedia(query, max_results=min(3, max_total))
    remaining = max_total - len(wiki_results)
    ddg_results = search_duckduckgo(query, max_results=remaining) if remaining > 0 else []

    all_results = wiki_results + ddg_results
    logger.info(
        "Free search for '%s': %d results (%d wiki, %d ddg)",
        query,
        len(all_results),
        len(wiki_results),
        len(ddg_results),
    )
    return all_results
