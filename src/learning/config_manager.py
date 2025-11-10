"""Configuration helper for dynamically updating sources.yaml."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Optional

import yaml


class ConfigManager:
    """Provides programmatic access to sources configuration."""

    def __init__(self, config_path: Path) -> None:
        self.config_path = Path(config_path)
        self.data: Dict[str, Any] = self._load()

    # ------------------------------------------------------------------
    # Core persistence helpers
    # ------------------------------------------------------------------
    def _load(self) -> Dict[str, Any]:
        if not self.config_path.exists():
            return {}
        with open(self.config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def save(self) -> None:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(self.data, f, allow_unicode=True, sort_keys=False)

    # ------------------------------------------------------------------
    # Source operations
    # ------------------------------------------------------------------
    def add_source(self, source: Dict[str, Any]) -> bool:
        """Add a new source entry based on its type."""

        source_type = source.get("type", "website")
        name = source.get("name") or self._derive_name_from_url(source.get("url", ""))
        url = source.get("url")

        if not url:
            return False

        if source_type == "github":
            repo_path = self._extract_repo_path(url)
            if not repo_path:
                return False
            repos = self.data.setdefault("github_repos", [])
            if any(entry.get("repo") == repo_path for entry in repos):
                return False
            repos.append(
                {
                    "name": name,
                    "repo": repo_path,
                    "category": "discovered",
                    "priority": 7,
                    "note": source.get("reason", "auto-discovered"),
                }
            )
            return True

        if source_type == "twitter":
            twitter_cfg = self.data.setdefault("twitter", {})
            accounts = twitter_cfg.setdefault("accounts", [])
            handle = self._extract_twitter_handle(url)
            if handle and handle not in accounts:
                accounts.append(handle)
                return True
            return False

        if source_type == "rss":
            feeds = self.data.setdefault("rss_feeds", [])
            if any(entry.get("url") == url for entry in feeds):
                return False
            feeds.append(
                {
                    "name": name,
                    "url": url,
                    "category": "discovered",
                    "priority": 8,
                    "note": source.get("reason", "auto-discovered"),
                }
            )
            return True

        # Default to news_feeds for website/newsletter sources
        feeds = self.data.setdefault("news_feeds", [])
        if any(entry.get("url") == url for entry in feeds):
            return False
        feeds.append(
            {
                "name": name,
                "url": url,
                "category": source.get("category", "ai-news"),
                "priority": 8,
                "note": source.get("reason", "auto-discovered"),
            }
        )
        return True

    def disable_source(self, name: str) -> bool:
        """Disable an existing source by name."""

        updated = False
        for section in ("rss_feeds", "news_feeds"):
            entries = self.data.get(section, [])
            for entry in entries:
                if entry.get("name") == name:
                    entry["enabled"] = False
                    updated = True

        repos = self.data.get("github_repos", [])
        for entry in repos:
            if entry.get("name") == name:
                entry["enabled"] = False
                updated = True

        return updated

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def reload(self) -> None:
        self.data = self._load()

    def _derive_name_from_url(self, url: str) -> str:
        if not url:
            return "Discovered Source"
        match = re.search(r"https?://([^/]+)/?", url)
        if match:
            host = match.group(1)
            return host.replace("www.", "")
        return url

    def _extract_repo_path(self, url: str) -> Optional[str]:
        match = re.search(r"github\.com/([^/]+/[^/]+)/?", url)
        return match.group(1) if match else None

    def _extract_twitter_handle(self, url: str) -> Optional[str]:
        match = re.search(r"twitter\.com/([^/?]+)", url) or re.search(r"x\.com/([^/?]+)", url)
        return match.group(1) if match else None


__all__ = ["ConfigManager"]
