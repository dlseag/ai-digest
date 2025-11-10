"""
Twitter Collector
从 Twitter 官方 API 代理 (twitterapi.io) 采集特定账号的高互动推文
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)


@dataclass
class TweetItem:
    """规范化后的推文条目"""

    title: str
    summary: str
    link: str
    published_date: str
    source: str
    category: str
    priority: int
    engagement: int
    author: str
    raw: Dict


class TwitterCollector:
    """
    Twitter 采集器

    使用 twitterapi.io 的 advanced_search 端点，过滤掉转推/回复，仅保留高互动原创内容。
    """

    API_URL = "https://api.twitterapi.io/twitter/tweet/advanced_search"

    def __init__(self, config: Dict):
        """
        Args:
            config: twitter 配置节
        """

        self.accounts: List[str] = config.get("accounts", [])
        self.min_engagement: int = int(config.get("min_engagement", 500))
        self.max_results: int = int(config.get("max_results_per_account", 5))
        self.within_hours: int = int(config.get("within_hours", 168))  # 默认 7 天
        self.priority: int = int(config.get("priority", 6))
        self.category: str = config.get("category", "community")
        self.sleep_between: float = float(config.get("sleep_seconds", 2))
        self.api_key: Optional[str] = config.get("api_key") or os.getenv("TWITTER_API_KEY")

        if not self.accounts:
            raise ValueError("TwitterCollector 需要配置至少一个 accounts")
        if not self.api_key:
            raise ValueError("未找到 TWITTER_API_KEY，请在环境变量或配置中提供")

    def collect(self) -> List[TweetItem]:
        """采集所有账号的推文"""

        tweets: List[TweetItem] = []

        for index, username in enumerate(self.accounts, 1):
            logger.info("Twitter采集 (%s/%s): @%s", index, len(self.accounts), username)
            try:
                items = self._fetch_account(username)
                tweets.extend(items)
            except Exception as exc:  # pragma: no cover - runtime logging
                logger.error("采集 @%s 失败: %s", username, exc)

            if index < len(self.accounts) and self.sleep_between > 0:
                time.sleep(self.sleep_between)

        logger.info("✓ Twitter采集完成: %s 条高互动推文", len(tweets))
        return tweets

    # ---------------------------------------------------------------------- #
    # 内部方法
    # ---------------------------------------------------------------------- #
    def _fetch_account(self, username: str) -> List[TweetItem]:
        """调用 twitterapi.io 获取单个账号的推文"""

        params = {
            "query": f"from:{username} -is:reply -is:retweet",
            "queryType": "Latest",
            "max_results": self.max_results,
            "within_time": f"{self.within_hours}h",
            "expansions": "referenced_tweets.id,author_id",
            "tweet.fields": "created_at,public_metrics,entities,referenced_tweets",
            "user.fields": "username,name,profile_image_url",
        }

        headers = {"X-API-Key": self.api_key}
        data = self._request_with_backoff(params, headers)

        tweets = data.get("tweets", [])
        includes = data.get("includes", {}) or {}
        users_lookup = {u["id"]: u for u in includes.get("users", [])}

        items: List[TweetItem] = []
        for tweet in tweets:
            try:
                if self._is_reply(tweet):
                    continue

                metrics = tweet.get("public_metrics", {})
                engagement = (
                    int(metrics.get("like_count", 0))
                    + int(metrics.get("retweet_count", 0))
                    + int(metrics.get("reply_count", 0))
                    + int(metrics.get("quote_count", 0))
                )
                if engagement < self.min_engagement:
                    continue

                author_id = tweet.get("author_id")
                author_info = users_lookup.get(author_id, {})
                author_name = author_info.get("name", username)
                handle = author_info.get("username", username)

                created_at = self._parse_datetime(tweet.get("created_at"))
                formatted_date = created_at.strftime("%Y-%m-%d %H:%M:%S") if created_at else ""

                text = self._clean_text(tweet.get("text", ""))
                if not text:
                    continue

                link = f"https://twitter.com/{handle}/status/{tweet.get('id')}"
                title = f"{author_name}: {text[:120]}{'…' if len(text) > 120 else ''}"

                tweet_item = TweetItem(
                    title=title,
                    summary=text,
                    link=link,
                    published_date=formatted_date,
                    source=f"Twitter · {author_name}",
                    category=self.category,
                    priority=self.priority,
                    engagement=engagement,
                    author=author_name,
                    raw=tweet,
                )
                items.append(tweet_item)
            except Exception as exc:  # pragma: no cover - log only
                logger.warning("处理 @%s 的推文时出错: %s", username, exc)

        # 按互动量排序
        items.sort(key=lambda item: item.engagement, reverse=True)
        return items

    def _request_with_backoff(self, params: Dict, headers: Dict, max_retries: int = 5) -> Dict:
        """带指数退避的请求"""

        delay = 5
        for attempt in range(1, max_retries + 1):
            try:
                resp = requests.get(self.API_URL, headers=headers, params=params, timeout=30)
                if resp.status_code == 429:
                    retry_after = resp.headers.get("Retry-After")
                    sleep_for = float(retry_after) if retry_after else delay
                    logger.warning("Twitter API 速率限制，%ss 后重试 (attempt %s)", sleep_for, attempt)
                    time.sleep(sleep_for)
                    delay = min(delay * 2, 60)
                    continue

                resp.raise_for_status()
                return resp.json()
            except requests.RequestException as exc:
                logger.warning("Twitter API 请求失败 (attempt %s/%s): %s", attempt, max_retries, exc)
                time.sleep(delay)
                delay = min(delay * 2, 60)

        raise RuntimeError("Twitter API 请求失败，超过最大重试次数")

    @staticmethod
    def _is_reply(tweet: Dict) -> bool:
        """判断推文是否为回复"""

        if tweet.get("in_reply_to_user_id") or tweet.get("in_reply_to_status_id"):
            return True

        for ref in tweet.get("referenced_tweets", []) or []:
            if ref.get("type") == "replied_to":
                return True

        return False

    @staticmethod
    def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
        if not value:
            return None
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.astimezone(timezone.utc)
        except Exception:
            return None

    @staticmethod
    def _clean_text(text: str) -> str:
        """简单清洗推文文本"""

        text = text.strip()
        # 去除过长链接/换行
        text = " ".join(text.split())
        return text


