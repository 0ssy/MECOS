"""
MECOS Free Search
=================
Pulls search results from Wikipedia and DuckDuckGo.
Zero API keys. Zero cost.

Dependencies:
    pip install requests beautifulsoup4 wikipedia-api
"""

import logging
import os
import time
from dataclasses import dataclass
from urllib.parse import parse_qs, unquote, urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "MECOSBot/1.0 (personal research assistant; github.com/0ssy/MECOS)"
}
DDG_COOLDOWN_SECONDS = int(os.getenv("MECOS_DDG_COOLDOWN_SECONDS", "1800"))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("MECOS_SEARCH_TIMEOUT_SECONDS", "15"))
REQUEST_RETRIES = int(os.getenv("MECOS_SEARCH_RETRIES", "2"))

_ddg_disabled_until = 0.0


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source: str  # "wikipedia" | "duckduckgo"


def _request_with_retry(method: str, url: str, **kwargs) -> requests.Response:
    last_error = None
    for attempt in range(REQUEST_RETRIES + 1):
        try:
            response = requests.request(method, url, **kwargs)
            response.raise_for_status()
            return response
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else None
            if status in (403, 429):
                raise
            last_error = exc
        except (
            requests.exceptions.ConnectTimeout,
            requests.exceptions.ReadTimeout,
            requests.exceptions.ConnectionError,
        ) as exc:
            last_error = exc

        if attempt < REQUEST_RETRIES:
            time.sleep(0.8 * (attempt + 1))

    if last_error:
        raise last_error
    raise RuntimeError(f"Request failed for {method} {url}")


def _decode_ddg_redirect(raw_url: str) -> str:
    if not raw_url:
        return ""
    if raw_url.startswith("//"):
        return "https:" + raw_url
    if raw_url.startswith("http://") or raw_url.startswith("https://"):
        return raw_url

    parsed = urlparse(raw_url)
    query = parse_qs(parsed.query)
    uddg = query.get("uddg", [])
    if uddg:
        return unquote(uddg[0])

    cleaned = raw_url.strip()
    if cleaned.startswith("www."):
        return "https://" + cleaned
    return ""


def _parse_ddg_html_results(html: str, max_results: int) -> list[SearchResult]:
    soup = BeautifulSoup(html, "html.parser")
    parsed_results: list[SearchResult] = []

    for result in soup.select(".result")[:max_results]:
        title_el = result.select_one("a.result__a")
        snippet_el = result.select_one(".result__snippet")
        if not title_el:
            continue
        title = title_el.get_text(strip=True)
        snippet = snippet_el.get_text(strip=True) if snippet_el else ""
        url = _decode_ddg_redirect(title_el.get("href", ""))
        if title and url:
            parsed_results.append(SearchResult(title=title, url=url, snippet=snippet, source="duckduckgo"))

    return parsed_results


def _parse_ddg_lite_results(html: str, max_results: int) -> list[SearchResult]:
    soup = BeautifulSoup(html, "html.parser")
    parsed_results: list[SearchResult] = []

    for link in soup.select("a[href]"):
        if len(parsed_results) >= max_results:
            break
        href = link.get("href", "")
        title = link.get_text(" ", strip=True)
        url = _decode_ddg_redirect(href)
        if not title or not url:
            continue
        parsed_results.append(SearchResult(title=title, url=url, snippet="", source="duckduckgo"))

    return parsed_results


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
        response = _request_with_retry(
            "GET",
            search_url,
            params=params,
            headers=HEADERS,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        items = response.json().get("query", {}).get("search", [])

        for item in items:
            title = item["title"]
            summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{title.replace(' ', '_')}"
            summary_response = requests.get(summary_url, headers=HEADERS, timeout=REQUEST_TIMEOUT_SECONDS)
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
    global _ddg_disabled_until

    now = time.time()
    if now < _ddg_disabled_until:
        logger.info("DuckDuckGo temporarily disabled for %.0fs due to previous block", _ddg_disabled_until - now)
        return []

    endpoints = [
        ("GET", "https://lite.duckduckgo.com/lite/", _parse_ddg_lite_results),
        ("POST", "https://html.duckduckgo.com/html/", _parse_ddg_html_results),
    ]

    for method, url, parser in endpoints:
        try:
            kwargs = {"headers": HEADERS, "timeout": REQUEST_TIMEOUT_SECONDS}
            if method == "GET":
                kwargs["params"] = {"q": query}
            else:
                kwargs["data"] = {"q": query, "b": ""}

            response = _request_with_retry(method, url, **kwargs)
            results = parser(response.text, max_results=max_results)
            if results:
                return results
        except requests.exceptions.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "unknown"
            if status in (403, 429):
                _ddg_disabled_until = time.time() + DDG_COOLDOWN_SECONDS
                logger.warning("DuckDuckGo blocked request (HTTP %s); backing off for %ds", status, DDG_COOLDOWN_SECONDS)
                return []
            logger.warning("DuckDuckGo endpoint failed (%s %s): %s", method, url, exc)
        except (
            requests.exceptions.ConnectTimeout,
            requests.exceptions.ReadTimeout,
            requests.exceptions.ConnectionError,
        ) as exc:
            logger.warning("DuckDuckGo endpoint timed out/unreachable (%s %s): %s", method, url, exc)
        except requests.exceptions.RequestException as exc:
            logger.warning("DuckDuckGo endpoint request failed (%s %s): %s", method, url, exc)

    return []


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
