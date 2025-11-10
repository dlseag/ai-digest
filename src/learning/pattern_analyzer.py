"""Behaviour pattern analysis for the learning engine."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.storage.feedback_db import FeedbackDB


class PatternAnalyzer:
    """Derives actionable insights from accumulated feedback signals."""

    def __init__(
        self,
        db: Optional[FeedbackDB] = None,
        window_days: int = 30,
        high_rate_threshold: float = 0.6,
        low_rate_threshold: float = 0.2,
        preferences: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.db = db or FeedbackDB()
        self.window_days = window_days
        self.high_rate_threshold = high_rate_threshold
        self.low_rate_threshold = low_rate_threshold
        self.preferences = preferences or {}
        self.protected_sources = set(self.preferences.get("protected_sources", []))
        self.dampened_sources = set(self.preferences.get("dampened_sources", []))

    def generate_insights(self, days: Optional[int] = None) -> Dict[str, Any]:
        summary = self.db.get_feedback_summary(days or self.window_days)
        sources = summary.get("sources", [])
        insights: List[str] = []
        priority_adjustments: List[Dict[str, Any]] = []

        if not sources:
            return {"insights": insights, "priority_adjustments": priority_adjustments}

        # Sort by high_rate descending for easier analysis
        sources_sorted = sorted(sources, key=lambda x: x["high_rate"], reverse=True)

        top_source = sources_sorted[0]
        if top_source["high_rate"] >= self.high_rate_threshold and top_source["total"] >= 5:
            if top_source["source"] in self.dampened_sources:
                insights.append(
                    f"{top_source['source']} 的命中率很高 (高质量占比 {top_source['high_rate']*100:.1f}%)，建议同时关注其他来源以保持多样性。"
                )
            else:
                insights.append(
                    f"你对 {top_source['source']} 的内容保持高度兴趣 (高质量占比 {top_source['high_rate']*100:.1f}%)。"
                )
                priority_adjustments.append(
                    {
                        "type": "adjust_priority",
                        "target": top_source["source"],
                        "direction": "increase",
                        "delta": 1,
                        "reason": "高相关率且交互频繁",
                    }
                )

        # Identify low performing sources
        for source in sources_sorted[::-1]:
            if source["total"] < 3:
                continue
            if source["high_rate"] <= self.low_rate_threshold:
                if source["source"] in self.protected_sources:
                    insights.append(
                        f"{source['source']} 最近相关性较低 (高质量占比 {source['high_rate']*100:.1f}%)，已按偏好保持现有优先级。"
                    )
                    continue
                insights.append(
                    f"{source['source']} 的内容相关性较低 (高质量占比 {source['high_rate']*100:.1f}%)，建议降低优先级或停用。"
                )
                priority_adjustments.append(
                    {
                        "type": "adjust_priority",
                        "target": source["source"],
                        "direction": "decrease",
                        "delta": 1,
                        "reason": "持续低相关",
                    }
                )
                break  # 限制单次报告的调整数量

        # Active hours insight
        hour_stats = summary.get("hours") or []
        if hour_stats:
            peak_hour = max(hour_stats, key=lambda x: x["total"])
            insights.append(
                f"你最常在 {peak_hour['hour']}:00 查看简报，建议将高价值摘要安排在该时间段前后。"
            )

        return {
            "insights": insights,
            "priority_adjustments": priority_adjustments,
        }


__all__ = ["PatternAnalyzer"]
