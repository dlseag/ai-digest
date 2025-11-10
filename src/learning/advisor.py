"""Advisor module to synthesise learning-driven recommendations."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from src.storage.feedback_db import FeedbackDB, OptimizationRecord
from src.learning.config_manager import ConfigManager

logger = logging.getLogger(__name__)


@dataclass
class Recommendation:
    """Structured recommendation for downstream presentation."""

    id: str
    title: str
    description: str
    recommendation_type: str
    target: str
    auto_apply: bool
    details: Dict[str, Any]
    estimated_impact: Optional[str] = None
    command: Optional[str] = None
    report_link: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        payload = {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "type": self.recommendation_type,
            "target": self.target,
            "auto_apply": self.auto_apply,
            "details": self.details,
            "estimated_impact": self.estimated_impact,
            "command": self.command,
            "report_link": self.report_link,
        }
        # Backwards compatibility for template fields
        payload.setdefault("reason", self.description)
        return payload


class Advisor:
    """Generates automatic and manual optimisation suggestions."""

    def __init__(
        self,
        db: Optional[FeedbackDB] = None,
        config: Optional[Dict[str, Any]] = None,
        project_root: Optional[Path] = None,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.db = db or FeedbackDB()
        self.config = config or {}
        self.project_root = project_root or Path(__file__).resolve().parents[2]
        self.config_manager = ConfigManager(self.project_root / "config" / "sources.yaml")
        self.preferences = preferences or {}
        self.protected_sources = set(self.preferences.get("protected_sources", []))

        thresholds = self.config.get("auto_optimization", {}).get("thresholds", {})
        self.auto_remove_quality = float(thresholds.get("auto_remove_source_quality", 3.0))
        self.auto_remove_useful_rate = float(thresholds.get("auto_remove_useful_rate", 0.3))
        self.auto_add_quality = float(thresholds.get("auto_add_source_quality", 8.5))
        self.min_quality_recommendation = float(
            self.config.get("source_discovery", {}).get("min_quality_for_recommendation", 7.0)
        )

    # ------------------------------------------------------------------
    # Recommendation lifecycle
    # ------------------------------------------------------------------
    def generate_and_apply_recommendations(self) -> Dict[str, List[Dict[str, Any]]]:
        """Produce optimisation suggestions and auto-apply safe ones."""

        self.config_manager.reload()
        auto_applied: List[Dict[str, Any]] = []
        require_review: List[Dict[str, Any]] = []

        auto_applied.extend(self._auto_disable_low_quality_sources())
        additions, manual_candidates = self._process_discovered_sources()
        auto_applied.extend(additions)
        require_review.extend(manual_candidates)

        return {
            "auto_applied": auto_applied,
            "require_review": require_review,
        }

    # ------------------------------------------------------------------
    # Autopilot operations
    # ------------------------------------------------------------------
    def _auto_disable_low_quality_sources(self) -> List[Dict[str, Any]]:
        recommendations: List[Dict[str, Any]] = []

        low_quality_sources = self.db.get_low_quality_sources(
            max_quality=self.auto_remove_quality,
            max_useful_rate=self.auto_remove_useful_rate,
        )

        for source in low_quality_sources:
            target = source["name"]
            if self.db.has_optimization("remove_source", target):
                continue
            if target in self.protected_sources:
                logger.debug("跳过受保护信息源的自动停用: %s", target)
                continue

            details = {
                "quality_score": source.get("quality_score"),
                "avg_relevance": source.get("avg_relevance"),
                "useful_rate": source.get("useful_rate"),
                "total_items": source.get("total_items"),
            }

            record = OptimizationRecord(
                optimization_type="remove_source",
                target=target,
                details=details,
            )
            self.db.log_optimization(record)

            if self.config_manager.disable_source(target):
                self.config_manager.save()

            recommendation = Recommendation(
                id=self._make_id("remove", target),
                title=f"已自动停用信息源：{target}",
                description=(
                    f"质量评分 {details['quality_score']}/10，" \
                    f"高相关率 {round(details['useful_rate'] * 100, 1)}%，" \
                    "已从后续采集中排除。"
                ),
                recommendation_type="remove_source",
                target=target,
                auto_apply=True,
                details=details,
                estimated_impact="降低噪音，聚焦高价值信号",
            )
            recommendations.append(recommendation.as_dict())

        return recommendations

    def _process_discovered_sources(self) -> (List[Dict[str, Any]], List[Dict[str, Any]]):
        auto_applied: List[Dict[str, Any]] = []
        require_review: List[Dict[str, Any]] = []

        discovered = self.db.get_pending_sources(self.min_quality_recommendation)

        for source in discovered:
            url = source.get("url")
            quality_score = source.get("quality_score")
            status = source.get("status", "pending")
            name = source.get("name") or url

            details = {
                "quality_score": quality_score,
                "relevance_score": source.get("relevance_score"),
                "update_frequency": source.get("update_frequency"),
                "reason": source.get("reason"),
                "discovered_from": source.get("discovered_from"),
                "type": source.get("type"),
            }

            if status == "auto_added_pending" and quality_score is not None:
                if self.db.has_optimization("add_source", url):
                    continue

                record = OptimizationRecord(
                    optimization_type="add_source",
                    target=url,
                    details={**details, "name": name},
                )
                self.db.log_optimization(record)
                self.db.update_discovered_source_status(url, "auto_added")

                if self.config_manager.add_source({**source, **details}):
                    self.config_manager.save()

                recommendation = Recommendation(
                    id=self._make_id("auto-add", url),
                    title=f"已自动纳入信息源：{name}",
                    description=(
                        f"质量评分 {quality_score}/10，已加入候选采集源。"
                    ),
                    recommendation_type="add_source",
                    target=url,
                    auto_apply=True,
                    details=details,
                    estimated_impact="拓展高质量信息来源",
                )
                auto_applied.append(recommendation.as_dict())
                continue

            # Manual review candidate
            recommendation = Recommendation(
                id=self._make_id("review-source", url),
                title=f"新增信息源候选：{name}",
                description=(
                    f"质量评分 {quality_score}/10，来源于 {source.get('discovered_from') or '最近文章'}。"
                ),
                recommendation_type="add_source",
                target=url,
                auto_apply=False,
                details=details,
                estimated_impact="潜在高价值信息源，待人工确认",
            )
            require_review.append(recommendation.as_dict())

        return auto_applied, require_review

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def _make_id(self, prefix: str, value: str) -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", value.lower())
        slug = slug.strip("-")[:40]
        return f"{prefix}-{slug}"


__all__ = ["Advisor", "Recommendation"]
