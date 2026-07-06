from __future__ import annotations

from app.web_search import (
    parse_searxng_results,
    parse_tavily_results,
    should_auto_web_search,
    with_search_context,
)


def test_should_auto_web_search_detects_realtime_queries():
    assert should_auto_web_search("\u4eca\u5929\u5929\u6c14\u600e\u4e48\u6837")
    assert should_auto_web_search("latest OpenAI news")
    assert should_auto_web_search("/search OpenAI")
    assert should_auto_web_search("/\u8054\u7f51 OpenAI")
    assert not should_auto_web_search("\u4f60\u597d\uff0c\u5e2e\u6211\u5199\u4e00\u53e5\u95ee\u5019")


def test_parse_searxng_results_filters_invalid_urls_and_limits():
    results = parse_searxng_results(
        {
            "results": [
                {"title": "A", "url": "https://example.com/a", "content": "alpha"},
                {"title": "Bad", "url": "javascript:alert(1)", "content": "bad"},
                {"title": "B", "url": "https://example.com/b", "content": "beta"},
            ]
        },
        limit=1,
    )

    assert len(results) == 1
    assert results[0].title == "A"
    assert results[0].url == "https://example.com/a"
    assert results[0].snippet == "alpha"


def test_parse_tavily_results_and_context_format():
    results = parse_tavily_results(
        {"results": [{"title": "A", "url": "https://example.com/a", "content": "alpha"}]},
        limit=5,
    )
    context = with_search_context("question", results)

    assert len(results) == 1
    assert "https://example.com/a" in context
    assert "question" in context
