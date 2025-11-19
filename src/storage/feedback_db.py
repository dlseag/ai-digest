"""SQLite-backed storage layer for the AI Digest learning engine."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional


@dataclass(frozen=True)
class OptimizationRecord:
    """Represents an optimization action applied by the learning engine."""

    optimization_type: str
    target: str
    details: Dict[str, Any]
    applied_at: Optional[datetime] = None


class FeedbackDB:
    """Persistence helper for learning-related signals and actions."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self.db_path = (db_path or project_root / "data" / "feedback.db").resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------
    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        conn = sqlite3.connect(self.db_path)
        try:
            conn.row_factory = sqlite3.Row
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                PRAGMA journal_mode=WAL;

                CREATE TABLE IF NOT EXISTS implicit_feedback (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id TEXT,
                    item_title TEXT,
                    item_source TEXT,
                    relevance_score REAL,
                    personal_priority REAL,
                    deep_dive_recommended INTEGER,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS source_performance (
                    source_name TEXT PRIMARY KEY,
                    total_items INTEGER DEFAULT 0,
                    high_relevance_items INTEGER DEFAULT 0,
                    avg_relevance REAL DEFAULT 0,
                    quality_score REAL DEFAULT 0,
                    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS discovered_sources (
                    url TEXT PRIMARY KEY,
                    name TEXT,
                    type TEXT,
                    quality_score REAL,
                    relevance_score REAL,
                    update_frequency TEXT,
                    reason TEXT,
                    status TEXT DEFAULT 'pending',
                    discovered_from TEXT,
                    discovered_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    added_at DATETIME
                );

                CREATE TABLE IF NOT EXISTS model_evaluations (
                    model_name TEXT PRIMARY KEY,
                    performance_score REAL,
                    cost_estimate TEXT,
                    comparison TEXT,
                    recommendation TEXT,
                    integration_difficulty TEXT,
                    recommended_use_cases TEXT,
                    status TEXT DEFAULT 'pending',
                    evaluated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS optimization_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    optimization_type TEXT,
                    target TEXT,
                    details TEXT,
                    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    rollback_at DATETIME
                );

                CREATE TABLE IF NOT EXISTS topic_trends (
                    topic TEXT PRIMARY KEY,
                    keywords TEXT,
                    total_mentions INTEGER DEFAULT 0,
                    last_window_mentions INTEGER DEFAULT 0,
                    first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_seen DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE TABLE IF NOT EXISTS few_shot_corrections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    correction_type TEXT,
                    original_output TEXT,
                    corrected_output TEXT,
                    article_context TEXT,
                    article_embedding TEXT,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_few_shot_type ON few_shot_corrections(correction_type, created_at DESC);

                CREATE TABLE IF NOT EXISTS ab_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    experiment_id TEXT,
                    variant TEXT,
                    metric_name TEXT,
                    metric_value REAL,
                    recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_ab_metrics_exp ON ab_metrics(experiment_id, variant);

                CREATE TABLE IF NOT EXISTS reading_behaviors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    report_id TEXT,
                    item_id TEXT,
                    action TEXT,
                    feedback_type TEXT,
                    section TEXT,
                    read_time INTEGER,
                    url TEXT,
                    metadata TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                );

                CREATE INDEX IF NOT EXISTS idx_reading_behaviors_item ON reading_behaviors(item_id, timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_reading_behaviors_report ON reading_behaviors(report_id, timestamp DESC);
                CREATE INDEX IF NOT EXISTS idx_reading_behaviors_action ON reading_behaviors(action, timestamp DESC);
                """
            )

    # ------------------------------------------------------------------
    # Feedback signals
    # ------------------------------------------------------------------
    def record_implicit_feedback(self, entry: Dict[str, Any]) -> None:
        """Persist a single implicit feedback entry and update aggregates."""

        source = entry.get("item_source") or "unknown"
        relevance = entry.get("relevance_score")
        relevance = float(relevance) if relevance is not None else 0.0

        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO implicit_feedback (
                    item_id,
                    item_title,
                    item_source,
                    relevance_score,
                    personal_priority,
                    deep_dive_recommended
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.get("item_id"),
                    entry.get("item_title"),
                    source,
                    relevance,
                    entry.get("personal_priority"),
                    1 if entry.get("deep_dive_recommended") else 0,
                ),
            )

            row = conn.execute(
                "SELECT total_items, high_relevance_items, avg_relevance FROM source_performance WHERE source_name = ?",
                (source,),
            ).fetchone()

            total_items = 0
            high_relevance_items = 0
            avg_relevance = 0.0

            if row:
                total_items = int(row["total_items"] or 0)
                high_relevance_items = int(row["high_relevance_items"] or 0)
                avg_relevance = float(row["avg_relevance"] or 0.0)

            total_items += 1
            if relevance >= 8:
                high_relevance_items += 1

            avg_relevance = ((avg_relevance * (total_items - 1)) + relevance) / total_items
            quality_score = round((high_relevance_items / total_items) * 10, 2)

            conn.execute(
                """
                INSERT INTO source_performance (
                    source_name,
                    total_items,
                    high_relevance_items,
                    avg_relevance,
                    quality_score,
                    last_updated
                ) VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(source_name) DO UPDATE SET
                    total_items = excluded.total_items,
                    high_relevance_items = excluded.high_relevance_items,
                    avg_relevance = excluded.avg_relevance,
                    quality_score = excluded.quality_score,
                    last_updated = CURRENT_TIMESTAMP
                """,
                (source, total_items, high_relevance_items, avg_relevance, quality_score),
            )

    # ------------------------------------------------------------------
    # Source quality analytics
    # ------------------------------------------------------------------
    def get_source_performance(self, source_name: str) -> Optional[Dict[str, Any]]:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM source_performance WHERE source_name = ?",
                (source_name,),
            ).fetchone()
            return dict(row) if row else None

    def get_low_quality_sources(
        self,
        max_quality: float,
        max_useful_rate: float,
        min_observations: int = 3,
    ) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM source_performance WHERE total_items >= ?",
                (min_observations,),
            ).fetchall()

        results: List[Dict[str, Any]] = []
        for row in rows:
            total = row["total_items"] or 0
            high = row["high_relevance_items"] or 0
            useful_rate = high / total if total else 0
            if (row["quality_score"] or 0) <= max_quality or useful_rate <= max_useful_rate:
                results.append(
                    {
                        "name": row["source_name"],
                        "total_items": total,
                        "high_relevance_items": high,
                        "quality_score": row["quality_score"],
                        "avg_relevance": row["avg_relevance"],
                        "useful_rate": useful_rate,
                    }
                )
        return results

    def save_discovered_source(
        self,
        source: Dict[str, Any],
        quality: Dict[str, Any],
        status: str = "pending",
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO discovered_sources (
                    url,
                    name,
                    type,
                    quality_score,
                    relevance_score,
                    update_frequency,
                    reason,
                    status,
                    discovered_from,
                    discovered_at,
                    added_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, NULL)
                ON CONFLICT(url) DO UPDATE SET
                    name = excluded.name,
                    type = excluded.type,
                    quality_score = excluded.quality_score,
                    relevance_score = excluded.relevance_score,
                    update_frequency = excluded.update_frequency,
                    reason = excluded.reason,
                    status = excluded.status,
                    discovered_from = excluded.discovered_from,
                    discovered_at = excluded.discovered_at
                """,
                (
                    source.get("url"),
                    source.get("name"),
                    source.get("type"),
                    quality.get("quality_score"),
                    quality.get("relevance_score"),
                    quality.get("update_frequency"),
                    quality.get("reason"),
                    status,
                    source.get("discovered_from"),
                ),
            )

    def update_discovered_source_status(self, url: str, status: str) -> None:
        with self._connect() as conn:
            if status == "auto_added":
                conn.execute(
                    "UPDATE discovered_sources SET status = ?, added_at = COALESCE(added_at, CURRENT_TIMESTAMP) WHERE url = ?",
                    (status, url),
                )
            else:
                conn.execute(
                    "UPDATE discovered_sources SET status = ? WHERE url = ?",
                    (status, url),
                )

    def get_pending_sources(self, min_quality: float) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT * FROM discovered_sources
                WHERE (status = 'pending' OR status = 'auto_added_pending')
                  AND (quality_score IS NULL OR quality_score >= ?)
                ORDER BY discovered_at DESC
                """,
                (min_quality,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_discovered_urls(self) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT url FROM discovered_sources").fetchall()
        return [row["url"] for row in rows]

    # ------------------------------------------------------------------
    # Model evaluations
    # ------------------------------------------------------------------
    def save_model_evaluation(self, evaluation: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO model_evaluations (
                    model_name,
                    performance_score,
                    cost_estimate,
                    comparison,
                    recommendation,
                    integration_difficulty,
                    recommended_use_cases,
                    status,
                    evaluated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(model_name) DO UPDATE SET
                    performance_score = excluded.performance_score,
                    cost_estimate = excluded.cost_estimate,
                    comparison = excluded.comparison,
                    recommendation = excluded.recommendation,
                    integration_difficulty = excluded.integration_difficulty,
                    recommended_use_cases = excluded.recommended_use_cases,
                    status = excluded.status,
                    evaluated_at = CURRENT_TIMESTAMP
                """,
                (
                    evaluation.get("model_name"),
                    evaluation.get("performance_score"),
                    evaluation.get("cost_estimate"),
                    json.dumps(evaluation.get("comparison"), ensure_ascii=False)
                    if isinstance(evaluation.get("comparison"), (dict, list))
                    else evaluation.get("comparison"),
                    evaluation.get("recommendation"),
                    evaluation.get("integration_difficulty"),
                    json.dumps(evaluation.get("recommended_use_cases"), ensure_ascii=False)
                    if isinstance(evaluation.get("recommended_use_cases"), (dict, list))
                    else evaluation.get("recommended_use_cases"),
                    evaluation.get("status", "pending"),
                ),
            )

    def list_evaluated_models(self) -> List[str]:
        with self._connect() as conn:
            rows = conn.execute("SELECT model_name FROM model_evaluations").fetchall()
        return [row["model_name"] for row in rows]

    def update_model_status(self, model_name: str, status: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "UPDATE model_evaluations SET status = ?, evaluated_at = CURRENT_TIMESTAMP WHERE model_name = ?",
                (status, model_name),
            )

    # ------------------------------------------------------------------
    # Optimization history & summaries
    # ------------------------------------------------------------------
    def log_optimization(self, record: OptimizationRecord | Dict[str, Any]) -> None:
        if isinstance(record, dict):
            record = OptimizationRecord(
                optimization_type=record.get("type") or record.get("optimization_type"),
                target=record.get("target", ""),
                details=record.get("details") or {},
                applied_at=record.get("applied_at"),
            )

        applied_at = record.applied_at or datetime.utcnow()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO optimization_history (
                    optimization_type,
                    target,
                    details,
                    applied_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    record.optimization_type,
                    record.target,
                    json.dumps(record.details, ensure_ascii=False),
                    applied_at.isoformat(timespec="seconds"),
                ),
            )

    def get_optimizations_since(self, days: int, types: Optional[Iterable[str]] = None) -> List[Dict[str, Any]]:
        cutoff = datetime.utcnow() - timedelta(days=days)
        type_clause = ""
        params: List[Any] = [cutoff.isoformat(timespec="seconds")]
        if types:
            types_tuple = tuple(types)
            placeholders = ",".join(["?"] * len(types_tuple))
            type_clause = f" AND optimization_type IN ({placeholders})"
            params.extend(types_tuple)

        with self._connect() as conn:
            rows = conn.execute(
                f"""
                SELECT * FROM optimization_history
                WHERE applied_at >= ?{type_clause}
                ORDER BY applied_at DESC
                """,
                params,
            ).fetchall()
        return [self._deserialize_optimization(row) for row in rows]

    def has_optimization(self, optimization_type: str, target: str) -> bool:
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT 1 FROM optimization_history
                WHERE optimization_type = ? AND target = ?
                ORDER BY applied_at DESC
                LIMIT 1
                """,
                (optimization_type, target),
            ).fetchone()
        return row is not None

    # ------------------------------------------------------------------
    # Topic trend tracking
    # ------------------------------------------------------------------
    def update_topic_trend(self, topic: str, keywords: List[str], window_mentions: int) -> None:
        if window_mentions <= 0:
            return

        keywords_json = json.dumps(keywords, ensure_ascii=False)
        with self._connect() as conn:
            row = conn.execute(
                "SELECT total_mentions FROM topic_trends WHERE topic = ?",
                (topic,),
            ).fetchone()

            if row:
                total = int(row["total_mentions"] or 0) + window_mentions
                conn.execute(
                    """
                    UPDATE topic_trends
                    SET keywords = ?,
                        total_mentions = ?,
                        last_window_mentions = ?,
                        last_seen = CURRENT_TIMESTAMP
                    WHERE topic = ?
                    """,
                    (keywords_json, total, window_mentions, topic),
                )
            else:
                conn.execute(
                    """
                    INSERT INTO topic_trends (
                        topic,
                        keywords,
                        total_mentions,
                        last_window_mentions,
                        first_seen,
                        last_seen
                    ) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    """,
                    (topic, keywords_json, window_mentions, window_mentions),
                )

    def get_emerging_topics(self, min_recent: int = 3, limit: int = 5) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT topic,
                       keywords,
                       total_mentions,
                       last_window_mentions,
                       first_seen,
                       last_seen
                FROM topic_trends
                WHERE last_window_mentions >= ?
                ORDER BY last_window_mentions DESC, last_seen DESC
                LIMIT ?
                """,
                (min_recent, limit),
            ).fetchall()

        results: List[Dict[str, Any]] = []
        for row in rows:
            keywords: List[str]
            raw_keywords = row["keywords"]
            try:
                keywords = json.loads(raw_keywords) if raw_keywords else []
            except json.JSONDecodeError:
                keywords = [raw_keywords]

            results.append(
                {
                    "topic": row["topic"],
                    "keywords": keywords,
                    "total_mentions": row["total_mentions"],
                    "recent_mentions": row["last_window_mentions"],
                    "first_seen": row["first_seen"],
                    "last_seen": row["last_seen"],
                }
            )
        return results

    def save_reading_behavior(self, behavior: Dict[str, Any]) -> None:
        """保存阅读行为数据"""
        with self._connect() as conn:
            metadata_json = json.dumps(behavior.get("metadata", {}))
            conn.execute(
                """
                INSERT INTO reading_behaviors (
                    report_id,
                    item_id,
                    action,
                    feedback_type,
                    section,
                    read_time,
                    url,
                    metadata
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    behavior.get("report_id"),
                    behavior.get("item_id"),
                    behavior.get("action"),
                    behavior.get("feedback_type"),
                    behavior.get("section"),
                    behavior.get("read_time"),
                    behavior.get("url"),
                    metadata_json,
                ),
            )

    def get_behaviors(
        self,
        *,
        report_id: Optional[str] = None,
        item_id: Optional[str] = None,
        action: Optional[str] = None,
        days: int = 7,
    ) -> List[Dict[str, Any]]:
        """获取行为数据"""
        with self._connect() as conn:
            conditions = []
            params = []
            
            if report_id:
                conditions.append("report_id = ?")
                params.append(report_id)
            if item_id:
                conditions.append("item_id = ?")
                params.append(item_id)
            if action:
                conditions.append("action = ?")
                params.append(action)
            
            conditions.append("timestamp >= datetime('now', '-' || ? || ' days')")
            params.append(days)
            
            where_clause = " AND ".join(conditions) if conditions else "1=1"
            
            rows = conn.execute(
                f"""
                SELECT * FROM reading_behaviors
                WHERE {where_clause}
                ORDER BY timestamp DESC
                """,
                params,
            ).fetchall()
            
            return [dict(row) for row in rows]

    def save_few_shot_correction(self, record: Dict[str, Any]) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO few_shot_corrections (
                    correction_type,
                    original_output,
                    corrected_output,
                    article_context,
                    article_embedding
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    record.get("correction_type", "analysis"),
                    record.get("original_output", ""),
                    record.get("corrected_output", ""),
                    record.get("article_context", ""),
                    json.dumps(record.get("article_embedding", []), ensure_ascii=False),
                ),
            )

    def fetch_few_shot_corrections(
        self,
        correction_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if correction_type:
                rows = conn.execute(
                    """
                    SELECT id, correction_type, original_output, corrected_output, article_context, article_embedding, created_at
                    FROM few_shot_corrections
                    WHERE correction_type = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (correction_type, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT id, correction_type, original_output, corrected_output, article_context, article_embedding, created_at
                    FROM few_shot_corrections
                    ORDER BY created_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

        results: List[Dict[str, Any]] = []
        for row in rows:
            embedding_raw = row["article_embedding"]
            try:
                embedding = json.loads(embedding_raw) if embedding_raw else []
            except json.JSONDecodeError:
                embedding = []
            results.append(
                {
                    "id": row["id"],
                    "correction_type": row["correction_type"],
                    "original_output": row["original_output"],
                    "corrected_output": row["corrected_output"],
                    "article_context": row["article_context"],
                    "article_embedding": embedding,
                    "created_at": row["created_at"],
                }
            )
        return results

    def log_ab_metric(
        self,
        experiment_id: str,
        variant: str,
        metric_name: str,
        metric_value: float,
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO ab_metrics (
                    experiment_id,
                    variant,
                    metric_name,
                    metric_value
                ) VALUES (?, ?, ?, ?)
                """,
                (experiment_id, variant, metric_name, float(metric_value)),
            )

    def fetch_ab_metrics(
        self,
        experiment_id: str,
        metric_name: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            if metric_name:
                rows = conn.execute(
                    """
                    SELECT variant, metric_value
                    FROM ab_metrics
                    WHERE experiment_id = ? AND metric_name = ?
                    ORDER BY recorded_at DESC
                    """,
                    (experiment_id, metric_name),
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT variant, metric_name, metric_value
                    FROM ab_metrics
                    WHERE experiment_id = ?
                    ORDER BY recorded_at DESC
                    """,
                    (experiment_id,),
                ).fetchall()

        metrics: List[Dict[str, Any]] = []
        for row in rows:
            entry = {"variant": row["variant"], "metric_value": row["metric_value"]}
            if metric_name:
                entry["metric_name"] = metric_name
            elif "metric_name" in row.keys():
                entry["metric_name"] = row["metric_name"]
            metrics.append(entry)
        return metrics

    def _deserialize_optimization(self, row: sqlite3.Row) -> Dict[str, Any]:
        details = row["details"]
        try:
            details_data = json.loads(details) if details else {}
        except json.JSONDecodeError:
            details_data = {"raw": details}

        return {
            "id": row["id"],
            "optimization_type": row["optimization_type"],
            "target": row["target"],
            "details": details_data,
            "applied_at": row["applied_at"],
            "rollback_at": row["rollback_at"],
        }

    # Weekly summary helpers ------------------------------------------------
    def get_sources_added_last_7_days(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT ds.url, ds.name, ds.quality_score, oh.applied_at
                FROM optimization_history oh
                JOIN discovered_sources ds ON ds.url = oh.target
                WHERE oh.optimization_type = 'add_source'
                  AND oh.applied_at >= datetime('now', '-7 days')
                ORDER BY oh.applied_at DESC
                """,
            ).fetchall()
        return [dict(row) for row in rows]

    def get_sources_removed_last_7_days(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT oh.target AS source_name, oh.details, oh.applied_at
                FROM optimization_history oh
                WHERE oh.optimization_type = 'remove_source'
                  AND oh.applied_at >= datetime('now', '-7 days')
                ORDER BY oh.applied_at DESC
                """,
            ).fetchall()

        results: List[Dict[str, Any]] = []
        for row in rows:
            details = row["details"]
            try:
                detail_data = json.loads(details) if details else {}
            except json.JSONDecodeError:
                detail_data = {"raw": details}
            results.append(
                {
                    "name": row["source_name"],
                    "quality_score": detail_data.get("quality_score"),
                    "useful_rate": detail_data.get("useful_rate"),
                    "applied_at": row["applied_at"],
                }
            )
        return results

    def get_priority_adjustments_last_7_days(self) -> List[Dict[str, Any]]:
        optimizations = self.get_optimizations_since(7, types=["adjust_priority"])
        return optimizations

    def get_models_evaluated_last_7_days(self) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT model_name, performance_score, recommendation, evaluated_at
                FROM model_evaluations
                WHERE evaluated_at >= datetime('now', '-7 days')
                ORDER BY evaluated_at DESC
                """,
            ).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Feedback analytics for pattern analysis
    # ------------------------------------------------------------------
    def get_feedback_summary(self, days: int = 30) -> Dict[str, Any]:
        cutoff_clause = ""
        params: List[Any] = []
        if days > 0:
            cutoff_clause = " WHERE timestamp >= datetime('now', ?)"
            params.append(f"-{int(days)} days")

        with self._connect() as conn:
            source_stats = conn.execute(
                f"""
                SELECT item_source AS source,
                       COUNT(*) AS total,
                       SUM(CASE WHEN COALESCE(relevance_score, 0) >= 8 THEN 1 ELSE 0 END) AS high_relevance,
                       AVG(COALESCE(relevance_score, 0)) AS avg_relevance
                FROM implicit_feedback
                {cutoff_clause}
                GROUP BY item_source
                ORDER BY high_relevance DESC
                """,
                params,
            ).fetchall()

            hour_stats = conn.execute(
                f"""
                SELECT strftime('%H', timestamp) AS hour,
                       COUNT(*) AS total
                FROM implicit_feedback
                {cutoff_clause}
                GROUP BY hour
                ORDER BY hour
                """,
                params,
            ).fetchall()

        sources = [
            {
                "source": row["source"],
                "total": row["total"],
                "high_relevance": row["high_relevance"],
                "high_rate": (row["high_relevance"] or 0) / row["total"] if row["total"] else 0,
                "avg_relevance": row["avg_relevance"] or 0,
            }
            for row in source_stats
        ]

        hours = [
            {
                "hour": row["hour"],
                "total": row["total"],
            }
            for row in hour_stats
        ]

        return {"sources": sources, "hours": hours}


__all__ = ["FeedbackDB", "OptimizationRecord"]
