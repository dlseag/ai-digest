"""Discovery engine for uncovering new information sources."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set
from urllib.parse import urlparse

from src.storage.feedback_db import FeedbackDB, OptimizationRecord

logger = logging.getLogger(__name__)

URL_PATTERN = re.compile(r"https?://[\w\-._~:/?#\[\]@!$&'()*+,;=%]+", re.IGNORECASE)


@dataclass
class SourceCandidate:
    """A potential new information source discovered from content."""

    url: str
    type: str
    name: str
    discovered_from: Optional[str] = None


class SourceDiscoverer:
    """Extracts and evaluates candidate sources from processed items."""

    def __init__(
        self,
        db: Optional[FeedbackDB] = None,
        llm_client: Optional[Any] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.db = db or FeedbackDB()
        self.llm = llm_client
        self.config = config or {}

        self.min_quality = float(self.config.get("min_quality_for_recommendation", 7.0))
        self.auto_add_quality = float(self.config.get("auto_add_source_quality", 8.5))
        self.auto_add_enabled = bool(self.config.get("auto_add_enabled", True))
        self.max_sources_per_run = int(self.config.get("max_sources_per_run", 10))
        self.exclude_domains: Set[str] = {
            domain.lower()
            for domain in self.config.get("exclude_domains", ["youtube.com", "medium.com", "reddit.com"])
        }

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def discover_from_content(self, items: Iterable[Any]) -> Dict[str, Any]:
        """Discover and evaluate candidate sources from processed items."""

        discovered_urls = set(self.db.list_discovered_urls())
        candidates: Dict[str, SourceCandidate] = {}

        for item in items:
            text_blob = self._collect_text(item)
            if not text_blob:
                continue
            for url in self._extract_urls(text_blob):
                if url in discovered_urls or url in candidates:
                    continue
                parsed = urlparse(url)
                if not parsed.netloc or self._should_ignore_domain(parsed.netloc):
                    continue

                source_type = self._identify_source_type(parsed)
                candidate = SourceCandidate(
                    url=url,
                    type=source_type,
                    name=self._guess_name(parsed),
                    discovered_from=self._get(item, "title"),
                )
                candidates[url] = candidate

        if not candidates:
            return {"evaluated": 0, "auto_add_candidates": [], "saved": 0}

        evaluated = 0
        auto_add_candidates: List[Dict[str, Any]] = []

        for candidate in list(candidates.values())[: self.max_sources_per_run]:
            quality = self._evaluate_source_quality(candidate)
            status = "pending"

            if quality and quality.get("quality_score") is not None:
                quality_score = float(quality["quality_score"])
                if (
                    self.auto_add_enabled
                    and quality_score >= self.auto_add_quality
                ):
                    status = "auto_added_pending"
                    auto_add_candidates.append({**candidate.__dict__, **quality})
            else:
                quality = {
                    "quality_score": None,
                    "relevance_score": None,
                    "reason": "LLM evaluation unavailable",
                }

            self.db.save_discovered_source(candidate.__dict__, quality, status=status)
            evaluated += 1

        return {
            "evaluated": evaluated,
            "auto_add_candidates": auto_add_candidates,
            "saved": evaluated,
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _collect_text(self, item: Any) -> str:
        parts: List[str] = []
        for key in ("content", "description", "summary", "body"):
            value = self._get(item, key)
            if value:
                parts.append(str(value))

        extra_links = self._get(item, "links")
        if isinstance(extra_links, (list, tuple)):
            parts.extend(str(link) for link in extra_links)

        return "\n".join(parts)

    def _extract_urls(self, text: str) -> List[str]:
        return [match.group(0).rstrip(".,)") for match in URL_PATTERN.finditer(text or "")]

    def _identify_source_type(self, parsed) -> str:
        host = parsed.netloc.lower()
        path = parsed.path.lower()
        if "github.com" in host:
            return "github"
        if host.endswith(".rss") or path.endswith(".rss") or "feed" in path:
            return "rss"
        if host.endswith("x.com") or "twitter.com" in host:
            return "twitter"
        if host.endswith("substack.com"):
            return "newsletter"
        return "website"

    def _guess_name(self, parsed) -> str:
        domain = parsed.netloc.lower()
        if domain.startswith("www."):
            domain = domain[4:]
        return domain

    def _should_ignore_domain(self, domain: str) -> bool:
        domain = domain.lower()
        return any(domain.endswith(blocked) for blocked in self.exclude_domains)

    def _evaluate_source_quality(self, candidate: SourceCandidate) -> Optional[Dict[str, Any]]:
        prompt = self._build_evaluation_prompt(candidate)
        response_text = self._call_llm(prompt)
        if not response_text:
            return None

        try:
            data = json.loads(response_text)
            # Normalise keys
            data.setdefault("quality_score", data.get("score"))
            data.setdefault("relevance_score", data.get("relevance"))
            return data
        except json.JSONDecodeError:
            logger.warning("Failed to parse source quality JSON for %s", candidate.url)
            return None

    def _build_evaluation_prompt(self, candidate: SourceCandidate) -> str:
        return (
            "请从专业角度评估以下信息源的质量，输出JSON。\n"
            "字段: quality_score(0-10), relevance_score(0-10), update_frequency, reason.\n"
            f"URL: {candidate.url}\n"
            f"类型: {candidate.type}\n"
            "关注点: AI行业趋势、RAG、AI测试工具、开发者工作流。"
        )

    def _call_llm(self, prompt: str) -> Optional[str]:
        if self.llm is None:
            return None
        try:
            response = getattr(self.llm, "invoke", self.llm)(prompt)
        except Exception as err:  # pragma: no cover - fallback logging
            logger.warning("LLM evaluation failed: %s", err)
            return None

        if response is None:
            return None

        if isinstance(response, str):
            return response.strip()

        content = getattr(response, "content", None)
        if isinstance(content, str):
            return content.strip()
        if isinstance(content, list):
            text_parts: List[str] = []
            for block in content:
                if isinstance(block, dict) and block.get("type") == "text":
                    text_parts.append(block.get("text", ""))
            return "\n".join(text_parts).strip()

        return str(response)

    def _get(self, item: Any, key: str) -> Any:
        if isinstance(item, dict):
            return item.get(key)
        return getattr(item, key, None)


__all__ = ["SourceDiscoverer", "SourceCandidate"]
