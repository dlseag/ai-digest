from datetime import datetime

from src.collectors.market_insights_collector import (
    MarketInsightsCollector,
    MarketInsight,
)
from src.collectors.producthunt_collector import ProductHuntCollector
from src.collectors.rss_collector import RSSCollector, RSSItem
from src.collectors.hackernews_collector import HackerNewsCollector, HackerNewsItem


def test_market_insights_collector_deduplicates(monkeypatch):
    collector = MarketInsightsCollector(
        sources=[{"name": "TestSource", "url": "https://example.com", "category": "analysis"}]
    )

    def fake_collect(source, cutoff):
        base = {
            "source": source["name"],
            "summary": "summary",
            "category": source["category"],
        }
        return [
            MarketInsight(title="A", url="https://dup.com/", published_date="2025-01-01", **base),
            MarketInsight(title="B", url="https://dup.com", published_date="2025-01-02", **base),
            MarketInsight(title="C", url="https://unique.com", published_date="2025-01-03", **base),
        ]

    monkeypatch.setattr(collector, "_collect_single_source", fake_collect)

    insights = collector.collect(days_back=7)
    assert len(insights) == 2
    assert {i.title for i in insights} == {"A", "C"}


def test_producthunt_collector_deduplicates_api_results(monkeypatch):
    config = {
        "enabled": True,
        "min_upvotes": 0,
        "topics": ["artificial-intelligence"],
        "priority": 8,
    }
    collector = ProductHuntCollector(config)
    collector.api_token = "fake-token"

    duplicate_payload = [
        {
            "title": "Tool A",
            "link": "https://dup.com/",
            "source": "ProductHunt",
            "published_date": "2025-01-01",
            "summary": "desc",
            "category": "project",
            "priority": 8,
        },
        {
            "title": "Tool B",
            "link": "https://dup.com",
            "source": "ProductHunt",
            "published_date": "2025-01-02",
            "summary": "desc",
            "category": "project",
            "priority": 8,
        },
        {
            "title": "Tool C",
            "link": "https://unique.com",
            "source": "ProductHunt",
            "published_date": "2025-01-03",
            "summary": "desc",
            "category": "project",
            "priority": 8,
        },
    ]

    monkeypatch.setattr(collector, "_collect_from_api", lambda days: duplicate_payload)
    monkeypatch.setattr(collector, "_collect_from_rss", lambda days: [])

    products = collector.collect(days_back=7)
    assert len(products) == 2
    assert {p["title"] for p in products} == {"Tool A", "Tool C"}


def test_rss_collector_deduplicates(monkeypatch):
    sources = [{"name": "Test RSS", "url": "https://example.com/feed"}]
    collector = RSSCollector(sources)

    def fake_collect_source(source, cutoff):
        now = datetime.now()
        base = {
            "summary": "summary",
            "published": now,
            "source": source["name"],
            "category": "news",
            "priority": 8,
        }
        return [
            RSSItem(title="A", link="https://dup.com/", **base),
            RSSItem(title="B", link="https://dup.com", **base),
            RSSItem(title="C", link="https://unique.com", **base),
        ]

    monkeypatch.setattr(collector, "_collect_source", fake_collect_source)
    items = collector.collect_all(days_back=7, source_timeout=1)
    assert len(items) == 2
    assert {i.title for i in items} == {"A", "C"}


def test_hackernews_collector_deduplicates(monkeypatch):
    collector = HackerNewsCollector(query_tags=["ai"], min_points=0)

    def fake_search(tag, cutoff):
        now = datetime.now()
        base = {
            "summary": "summary",
            "published": now,
            "source": "Hacker News",
            "category": "community",
            "priority": 9,
            "points": 100,
            "comments": 50,
        }
        return [
            HackerNewsItem(title="A", link="https://dup.com/", **base),
            HackerNewsItem(title="B", link="https://dup.com", **base),
            HackerNewsItem(title="C", link="https://unique.com", **base),
        ]

    monkeypatch.setattr(collector, "_search_by_tag", fake_search)

    items = collector.collect(days_back=7)
    assert len(items) == 2
    assert {i.title for i in items} == {"A", "C"}

