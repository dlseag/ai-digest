"""
Data collectors for AI Weekly Report
数据采集器模块
"""

from .rss_collector import RSSCollector
from .github_collector import GitHubCollector
from .hackernews_collector import HackerNewsCollector
from .reddit_collector import RedditCollector
from .news_collector import NewsCollector
from .producthunt_collector import ProductHuntCollector
from .twitter_collector import TwitterCollector

__all__ = [
    "RSSCollector",
    "GitHubCollector",
    "HackerNewsCollector",
    "RedditCollector",
    "NewsCollector",
    "ProductHuntCollector",
    "TwitterCollector",
]

