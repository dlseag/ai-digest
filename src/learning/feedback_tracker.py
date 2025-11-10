"""Implicit feedback tracker for the AI Digest learning engine."""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from src.storage.feedback_db import FeedbackDB


class FeedbackTracker:
    """Captures implicit feedback signals from processed briefing items."""

    def __init__(
        self,
        db: Optional[FeedbackDB] = None,
        signals: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.db = db or FeedbackDB()
        default_signals: Dict[str, Any] = {
            "high_relevance": 8,
            "high_priority": 9,
            "deep_dive": True,
        }
        self.signals: Dict[str, Any] = {**default_signals, **(signals or {})}

    # ------------------------------------------------------------------
    # Recording feedback
    # ------------------------------------------------------------------
    def record_implicit_feedback(self, items: Iterable[Any]) -> None:
        """Persist implicit signals for a collection of processed items."""

        for item in items:
            entry = self._build_entry(item)
            if not entry:
                continue
            self.db.record_implicit_feedback(entry)

    # ------------------------------------------------------------------
    # Accessors & analytics
    # ------------------------------------------------------------------
    def get_source_quality(self, source_name: str) -> Optional[Dict[str, Any]]:
        return self.db.get_source_performance(source_name)

    def get_low_quality_sources(
        self,
        max_quality: float = 3.0,
        max_useful_rate: float = 0.3,
        min_observations: int = 3,
    ) -> List[Dict[str, Any]]:
        return self.db.get_low_quality_sources(max_quality, max_useful_rate, min_observations)

    @property
    def signal_thresholds(self) -> Dict[str, Any]:
        """Expose the active implicit feedback thresholds."""

        return dict(self.signals)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _build_entry(self, item: Any) -> Optional[Dict[str, Any]]:
        item_id = self._get(item, "id") or self._get(item, "item_id")
        source = self._get(item, "source")
        if not source:
            return None

        relevance = self._to_number(self._get(item, "relevance_score"))
        personal_priority = self._to_number(self._get(item, "personal_priority"))
        deep_dive = bool(self._get(item, "deep_dive_recommended"))

        return {
            "item_id": item_id,
            "item_title": self._get(item, "title"),
            "item_source": source,
            "relevance_score": relevance,
            "personal_priority": personal_priority,
            "deep_dive_recommended": deep_dive,
        }

    def _get(self, item: Any, key: str) -> Any:
        if isinstance(item, dict):
            return item.get(key)
        return getattr(item, key, None)

    def _to_number(self, value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None


__all__ = ["FeedbackTracker"]
