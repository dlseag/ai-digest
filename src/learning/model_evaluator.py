"""Model evaluation and monitoring utilities."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

from src.collectors.leaderboard_collector import LeaderboardCollector
from src.storage.feedback_db import FeedbackDB

logger = logging.getLogger(__name__)


@dataclass
class ModelEvaluation:
    """Represents a model evaluation result."""

    model_name: str
    performance_score: float
    cost_estimate: str
    comparison: Dict[str, Any]
    recommendation: str
    integration_difficulty: str
    recommended_use_cases: List[str]
    status: str = "pending"

    def as_dict(self) -> Dict[str, Any]:
        return {
            "model_name": self.model_name,
            "performance_score": self.performance_score,
            "cost_estimate": self.cost_estimate,
            "comparison": self.comparison,
            "recommendation": self.recommendation,
            "integration_difficulty": self.integration_difficulty,
            "recommended_use_cases": self.recommended_use_cases,
            "status": self.status,
        }


class ModelEvaluator:
    """Monitors leaderboards and evaluates promising models."""

    def __init__(
        self,
        db: Optional[FeedbackDB] = None,
        llm_client: Optional[Any] = None,
        leaderboard_collector: Optional[LeaderboardCollector] = None,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.db = db or FeedbackDB()
        self.llm = llm_client
        self.leaderboard_collector = leaderboard_collector or LeaderboardCollector()
        self.config = config or {}

        self.max_models_per_run = int(self.config.get("max_models_per_run", 5))
        self.performance_threshold = float(self.config.get("performance_threshold", 8.5))
        self.top_n = int(self.config.get("leaderboard_top_n", 15))

    def monitor_new_models(self) -> Dict[str, Any]:
        """Monitor leaderboards and evaluate models not yet reviewed."""

        leaderboard = self.leaderboard_collector.collect(top_n=self.top_n)
        if not leaderboard:
            logger.info("No leaderboard data available for model evaluation.")
            return {"evaluated": 0, "flagged": []}

        known_models = set(self.db.list_evaluated_models())
        evaluated_count = 0
        flagged: List[Dict[str, Any]] = []

        for entry in leaderboard:
            model_name = entry.get("model_name")
            if not model_name or model_name in known_models:
                continue

            evaluation = self._evaluate_model(entry)
            if evaluation is None:
                continue

            self.db.save_model_evaluation(evaluation.as_dict())
            evaluated_count += 1

            if evaluation.recommendation in {"strongly_recommend", "recommend"}:
                flagged.append(evaluation.as_dict())

            if evaluated_count >= self.max_models_per_run:
                break

        return {"evaluated": evaluated_count, "flagged": flagged}

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _evaluate_model(self, leaderboard_entry: Dict[str, Any]) -> Optional[ModelEvaluation]:
        model_name = leaderboard_entry.get("model_name")
        if not model_name:
            return None

        prompt = self._build_prompt(leaderboard_entry)
        response_text = self._call_llm(prompt)

        if response_text:
            try:
                data = json.loads(response_text)
                recommended_use_cases = data.get("recommended_use_cases") or []
                if isinstance(recommended_use_cases, str):
                    recommended_use_cases = [recommended_use_cases]

                return ModelEvaluation(
                    model_name=model_name,
                    performance_score=float(data.get("performance_score", leaderboard_entry.get("elo_score", 0) / 100)),
                    cost_estimate=data.get("cost_estimate", "unknown"),
                    comparison=data.get("comparison", {}),
                    recommendation=data.get("recommendation", "investigate"),
                    integration_difficulty=data.get("integration_difficulty", "unknown"),
                    recommended_use_cases=recommended_use_cases,
                    status=data.get("status", "pending"),
                )
            except json.JSONDecodeError:
                logger.warning("Model evaluation JSON parse failure for %s", model_name)

        # Heuristic fallback when LLM is unavailable
        elo_score = float(leaderboard_entry.get("elo_score", 0))
        performance_score = round(min(elo_score / 150.0, 10.0), 2)
        recommendation = "strongly_recommend" if performance_score >= self.performance_threshold else "investigate"

        return ModelEvaluation(
            model_name=model_name,
            performance_score=performance_score,
            cost_estimate="unknown",
            comparison={"elo_score": elo_score},
            recommendation=recommendation,
            integration_difficulty="medium",
            recommended_use_cases=["ai-digest", "mutation-test-killer"],
            status="pending",
        )

    def _build_prompt(self, leaderboard_entry: Dict[str, Any]) -> str:
        model_name = leaderboard_entry.get("model_name", "Unknown")
        elo = leaderboard_entry.get("elo_score")
        organization = leaderboard_entry.get("organization")
        return (
            "你是AI模型评估专家。请基于模型在LMSYS排行榜的表现评估其对David项目的价值。\n"
            "输出JSON，字段：performance_score(0-10)、cost_estimate、comparison(对象)、recommendation"
            "(strongly_recommend/recommend/investigate/not_recommend)、integration_difficulty(easy/medium/hard)、"
            "recommended_use_cases(数组)以及status(pending/reviewed)。\n"
            "背景：David关注 mutation-test-killer（AI测试）、ai-digest（情报简报）、rag-practics（RAG优化）。\n"
            f"模型名称: {model_name}\n"
            f"组织: {organization}\n"
            f"Elo评分: {elo}\n"
            "请简洁输出。"
        )

    def _call_llm(self, prompt: str) -> Optional[str]:
        if self.llm is None:
            return None
        try:
            response = getattr(self.llm, "invoke", self.llm)(prompt)
        except Exception as err:  # pragma: no cover - best effort logging
            logger.warning("Model evaluation LLM call failed: %s", err)
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


__all__ = ["ModelEvaluator", "ModelEvaluation"]
