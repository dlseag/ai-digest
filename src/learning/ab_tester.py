"""Utilities for lightweight A/B testing instrumentation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

import numpy as np
from scipy.stats import ttest_ind

from src.storage.feedback_db import FeedbackDB


@dataclass
class Experiment:
    id: str
    hypothesis: str
    metric: str
    variants: Dict[str, str]


@dataclass
class ExperimentResult:
    experiment_id: str
    metric: str
    control_mean: float
    treatment_mean: float
    p_value: float
    effect_size: float
    recommendation: str


class ABTester:
    def __init__(self, db: FeedbackDB) -> None:
        self.db = db

    def assign_variant(self, user_id: str, experiment: Experiment) -> str:
        variants = sorted(experiment.variants.keys())
        digest = hashlib.sha256(f"{user_id}:{experiment.id}".encode("utf-8")).hexdigest()
        index = int(digest, 16) % max(1, len(variants))
        return variants[index]

    def log_metric(
        self,
        experiment: Experiment,
        variant: str,
        value: float,
    ) -> None:
        self.db.log_ab_metric(experiment.id, variant, experiment.metric, value)

    def analyse(self, experiment: Experiment) -> Optional[ExperimentResult]:
        rows = self.db.fetch_ab_metrics(experiment.id, metric_name=experiment.metric)
        grouped: Dict[str, List[float]] = {}
        for row in rows:
            grouped.setdefault(row["variant"], []).append(row["metric_value"])

        control = grouped.get("control", [])
        treatment = grouped.get("treatment", [])
        if len(control) < 2 or len(treatment) < 2:
            return None

        control_arr = np.array(control, dtype=float)
        treatment_arr = np.array(treatment, dtype=float)
        _, p_value = ttest_ind(treatment_arr, control_arr, equal_var=False)
        effect = float(treatment_arr.mean() - control_arr.mean())

        recommendation = "need_more_data"
        if p_value < 0.05:
            recommendation = "adopt" if effect > 0 else "reject"

        return ExperimentResult(
            experiment_id=experiment.id,
            metric=experiment.metric,
            control_mean=float(control_arr.mean()),
            treatment_mean=float(treatment_arr.mean()),
            p_value=float(p_value),
            effect_size=effect,
            recommendation=recommendation,
        )

    def summarise(self, experiment: Experiment) -> str:
        result = self.analyse(experiment)
        if not result:
            return (
                f"Experiment {experiment.id}: insufficient data for analysis."
            )
        return (
            f"Experiment {result.experiment_id} ({experiment.metric}):\n"
            f"  Control mean: {result.control_mean:.3f}\n"
            f"  Treatment mean: {result.treatment_mean:.3f}\n"
            f"  Effect size: {result.effect_size:.3f}\n"
            f"  p-value: {result.p_value:.4f}\n"
            f"  Recommendation: {result.recommendation}"
        )


__all__ = ["ABTester", "Experiment", "ExperimentResult"]
