from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

import httpx


@dataclass(slots=True)
class WebSearchConfig:
    enabled: bool
    auto_enabled: bool
    provider: str
    base_url: str
    api_key: str
    result_count: int
    timeout_seconds: float


@dataclass(slots=True)
class WebSearchResult:
    title: str
    url: str
    snippet: str


REALTIME_MARKERS = (
    "\u4eca\u5929",
    "\u4eca\u65e5",
    "\u73b0\u5728",
    "\u521a\u521a",
    "\u6700\u65b0",
    "\u6700\u8fd1",
    "\u5b9e\u65f6",
    "\u65b0\u95fb",
    "\u70ed\u641c",
    "\u516c\u544a",
    "\u53d1\u5e03",
    "\u66f4\u65b0",
    "\u7248\u672c",
    "\u4ef7\u683c",
    "\u80a1\u4ef7",
    "\u6c47\u7387",
    "\u5929\u6c14",
    "\u8d5b\u7a0b",
    "\u6bd4\u5206",
    "\u653f\u7b56",
    "\u6cd5\u89c4",
    "\u5b98\u7f51",
    "\u94fe\u63a5",
    "\u67e5\u8be2",
    "\u67e5\u4e00\u4e0b",
    "\u641c\u4e00\u4e0b",
    "\u8054\u7f51",
)

ENGLISH_REALTIME_MARKERS = (
    "latest",
    "today",
    "news",
    "price",
    "weather",
    "schedule",
    "score",
    "current",
    "recent",
)


def should_auto_web_search(text: str) -> bool:
    normalized = text.strip().lower()
    if not normalized:
        return False
    if normalized.startswith(("/search", "/web", "/\u8054\u7f51", "/\u641c\u7d22")):
        return True
    if any(marker in normalized for marker in REALTIME_MARKERS):
        return True
    return any(marker in normalized for marker in ENGLISH_REALTIME_MARKERS)


class WebSearchService:
    def __init__(self, client: httpx.AsyncClient | None = None):
        self.client = client

    async def search(self, config: WebSearchConfig, query: str) -> list[WebSearchResult]:
        if not config.enabled:
            return []
        provider = config.provider.strip().lower()
        if provider in {"", "disabled"}:
            return []
        limit = max(1, min(config.result_count or 5, 10))
        if provider == "searxng":
            return await self._search_searxng(config, query, limit)
        if provider == "tavily":
            return await self._search_tavily(config, query, limit)
        raise ValueError(f"unsupported web search provider: {config.provider}")

    async def _search_searxng(
        self,
        config: WebSearchConfig,
        query: str,
        limit: int,
    ) -> list[WebSearchResult]:
        if not config.base_url:
            raise ValueError("web search base url is not configured")
        close_client = False
        client = self.client
        if client is None:
            client = httpx.AsyncClient(timeout=config.timeout_seconds)
            close_client = True
        try:
            response = await client.get(
                f"{config.base_url.rstrip('/')}/search",
                params={"q": query, "format": "json"},
            )
            response.raise_for_status()
            return parse_searxng_results(response.json(), limit)
        finally:
            if close_client:
                await client.aclose()

    async def _search_tavily(
        self,
        config: WebSearchConfig,
        query: str,
        limit: int,
    ) -> list[WebSearchResult]:
        if not config.base_url:
            raise ValueError("web search base url is not configured")
        if not config.api_key:
            raise ValueError("web search api key is not configured")
        close_client = False
        client = self.client
        if client is None:
            client = httpx.AsyncClient(timeout=config.timeout_seconds)
            close_client = True
        try:
            response = await client.post(
                f"{config.base_url.rstrip('/')}/search",
                json={
                    "api_key": config.api_key,
                    "query": query,
                    "max_results": limit,
                    "search_depth": "basic",
                    "include_answer": False,
                },
            )
            response.raise_for_status()
            return parse_tavily_results(response.json(), limit)
        finally:
            if close_client:
                await client.aclose()


def parse_searxng_results(payload: dict, limit: int) -> list[WebSearchResult]:
    rows = payload.get("results") if isinstance(payload, dict) else []
    results: list[WebSearchResult] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        result = make_result(
            title=row.get("title"),
            url=row.get("url"),
            snippet=row.get("content") or row.get("snippet"),
        )
        if result is not None:
            results.append(result)
        if len(results) >= limit:
            break
    return results


def parse_tavily_results(payload: dict, limit: int) -> list[WebSearchResult]:
    rows = payload.get("results") if isinstance(payload, dict) else []
    results: list[WebSearchResult] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, dict):
            continue
        result = make_result(
            title=row.get("title"),
            url=row.get("url"),
            snippet=row.get("content") or row.get("snippet"),
        )
        if result is not None:
            results.append(result)
        if len(results) >= limit:
            break
    return results


def make_result(title, url, snippet) -> WebSearchResult | None:
    url_text = str(url or "").strip()
    parsed = urlparse(url_text)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    title_text = str(title or parsed.hostname).strip()[:200]
    snippet_text = str(snippet or "").strip().replace("\n", " ")[:500]
    return WebSearchResult(title=title_text or parsed.hostname, url=url_text, snippet=snippet_text)


def format_search_context(results: list[WebSearchResult]) -> str:
    lines = []
    for index, result in enumerate(results, start=1):
        snippet = f"\nSummary: {result.snippet}" if result.snippet else ""
        lines.append(f"[{index}] {result.title}\nURL: {result.url}{snippet}")
    return "\n\n".join(lines)


def with_search_context(question: str, results: list[WebSearchResult]) -> str:
    return "\n\n".join(
        [
            (
                "Use the following web search results to answer the user's question. "
                "Prefer the search results for current facts, do not invent details, "
                "and include brief source links when useful."
            ),
            "User question:",
            question,
            "Web search results:",
            format_search_context(results),
        ]
    )
