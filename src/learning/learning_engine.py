"""High-level orchestrator for the AI Digest self-learning workflow."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from src.learning.advisor import Advisor
from src.learning.feedback_tracker import FeedbackTracker
from src.learning.model_evaluator import ModelEvaluator
from src.learning.pattern_analyzer import PatternAnalyzer
from src.learning.source_discoverer import SourceDiscoverer
from src.storage.feedback_db import FeedbackDB
from src.memory.user_profile_manager import UserProfileManager
from src.learning.fact_extractor import FactExtractor


class LearningEngine:
    """Coordinates feedback tracking, discovery, evaluation, and advice."""

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        llm_client: Optional[Any] = None,
        project_root: Optional[Path] = None,
        user_profile_manager: Optional[UserProfileManager] = None,
        api_key: Optional[str] = None,
    ) -> None:
        self.config = config or {}
        self.enabled = self.config.get("enabled", True)
        self.user_profile_manager = user_profile_manager
        self.api_key = api_key
        self.source_preferences = self.config.get("source_preferences", {})

        self.db = FeedbackDB()
        self.feedback_tracker = FeedbackTracker(
            db=self.db,
            signals=self.config.get("feedback_tracking", {}).get("signals"),
        )
        self.pattern_analyzer = PatternAnalyzer(
            db=self.db,
            window_days=self.config.get("analysis_window_days", 30),
            preferences=self.source_preferences,
        )
        self.source_discoverer = SourceDiscoverer(
            db=self.db,
            llm_client=llm_client,
            config=self.config,
        )
        self.model_evaluator = ModelEvaluator(
            db=self.db,
            llm_client=llm_client,
            config=self.config,
        )
        self.advisor = Advisor(
            db=self.db,
            config=self.config,
            project_root=project_root,
            preferences=self.source_preferences,
        )
        self.fact_extractor = (
            FactExtractor(api_key=self.api_key)
            if self.api_key and self.user_profile_manager
            else None
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def run_cycle(self, processed_items: Iterable[Any], is_weekly: bool = False) -> Dict[str, Any]:
        if not self.enabled:
            return {
                "auto_applied": [],
                "require_review": [],
                "insights": [],
                "discovery": {},
                "models": {},
                "weekly_summary": self.generate_weekly_summary() if is_weekly else None,
                "is_weekly": is_weekly,
            }

        processed_items = list(processed_items)
        self.feedback_tracker.record_implicit_feedback(processed_items)
        self._update_user_profile_vectors(processed_items)

        discovery_result = {}
        if self.config.get("source_discovery", {}).get("enabled", True):
            discovery_result = self.source_discoverer.discover_from_content(processed_items)

        model_result = {}
        if self.config.get("model_monitoring", {}).get("enabled", True):
            model_result = self.model_evaluator.monitor_new_models()

        advisor_result = self.advisor.generate_and_apply_recommendations()
        insights_payload = self.pattern_analyzer.generate_insights()

        weekly_summary = self.generate_weekly_summary() if is_weekly else None

        return {
            "auto_applied": advisor_result["auto_applied"],
            "require_review": advisor_result["require_review"],
            "insights": insights_payload.get("insights", []),
            "priority_adjustments": insights_payload.get("priority_adjustments", []),
            "discovery": discovery_result,
            "models": model_result,
            "weekly_summary": weekly_summary,
            "is_weekly": is_weekly,
        }

    def generate_weekly_summary(self) -> Dict[str, Any]:
        return {
            "sources_added": self.db.get_sources_added_last_7_days(),
            "sources_removed": self.db.get_sources_removed_last_7_days(),
            "priority_adjustments": self.db.get_priority_adjustments_last_7_days(),
            "models_evaluated": self.db.get_models_evaluated_last_7_days(),
            "generated_at": datetime.utcnow().isoformat(timespec="seconds"),
        }

    def _update_user_profile_vectors(self, processed_items: Iterable[Any]) -> None:
        if not self.user_profile_manager:
            return

        thresholds = self.feedback_tracker.signal_thresholds
        high_priority_threshold = thresholds.get("high_priority", 8)

        updates_performed = False
        positive_items: List[Any] = []
        for item in processed_items:
            personal_priority = self._safe_number(getattr(item, "personal_priority", None) if not isinstance(item, dict) else item.get("personal_priority"))
            deep_dive = getattr(item, "deep_dive_recommended", None) if not isinstance(item, dict) else item.get("deep_dive_recommended")

            if personal_priority is not None and personal_priority >= high_priority_threshold or deep_dive:
                text = self._compose_feedback_text(item)
                if text:
                    self.user_profile_manager.update_implicit_vector(text, positive=True)
                    updates_performed = True
                    positive_items.append(item)

        if updates_performed:
            self.user_profile_manager.save_vectors()
            self._extract_preference_facts(positive_items)

    def _compose_feedback_text(self, item: Any) -> str:
        if isinstance(item, dict):
            title = item.get("title", "")
            summary = item.get("summary") or item.get("ai_summary") or ""
            why = item.get("why_matters_to_you") or item.get("impact_analysis") or ""
        else:
            title = getattr(item, "title", "")
            summary = getattr(item, "summary", None) or getattr(item, "ai_summary", "")
            why = getattr(item, "why_matters_to_you", "") or getattr(item, "impact_analysis", "")
        parts = [title, summary, why]
        return "\n".join(part for part in parts if part).strip()

    def _safe_number(self, value: Any) -> Optional[float]:
        if value in (None, ""):
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    def _extract_preference_facts(self, items: Iterable[Any]) -> None:
        if not self.fact_extractor or not self.user_profile_manager:
            return
        facts = self.fact_extractor.extract(items, self.user_profile_manager.get_profile())
        if facts:
            self.user_profile_manager.add_preference_facts(facts)


__all__ = ["LearningEngine"]
