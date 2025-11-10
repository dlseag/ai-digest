import logging
from typing import Dict, List, Optional, Set

import numpy as np
# 禁用导入，避免触发 transformers 锁问题
# from sentence_transformers import SentenceTransformer
SentenceTransformer = None

from ai_digest.db.feedback_db import FeedbackDB
from ai_digest.models.cluster_summary import ClusterSummary

logger = logging.getLogger(__name__)


class ProactiveAgent:
    """Use topic trend analytics to suggest proactive next steps."""

    def __init__(self, db: Optional[FeedbackDB] = None) -> None:
        self.db = db or FeedbackDB()
        self._embedder = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")

    def generate_suggestions(
        self,
        clusters: Dict[str, ClusterSummary],
        *,
        user_profile: Optional[Dict] = None,
        limit: int = 3,
        min_recent_mentions: int = 2,
    ) -> List[Dict]:
        """
        Update topic trends based on current clusters and surface suggestions.
        """
        emerging = self.db.get_emerging_topics(
            min_recent=max(1, min_recent_mentions),
            limit=limit,
        )

        suggestions: List[Dict] = []
        titles_added: Set[str] = set()

        for topic in emerging:
            reason = (
                f"本周期提及 {topic['recent_mentions']} 次，累计 {topic['total_mentions']} 次。"
            )
            title = f"跟踪新兴主题：{topic['topic']}"
            suggestions.append(
                {
                    "title": title,
                    "reason": reason,
                    "action": "建议纳入监控列表，并评估是否需要安排深度研究。",
                    "related_topics": topic.get("keywords", []),
                }
            )
            titles_added.add(title)

        # Highlight weak signals (noise cluster) if small but unique
        weak_signal_cluster = clusters.get("-1")
        if weak_signal_cluster and weak_signal_cluster.item_ids:
            title = "关注弱信号"
            if title not in titles_added:
                suggestions.append(
                    {
                        "title": title,
                        "reason": "这些内容目前未形成主流话题，但可能包含早期趋势。",
                        "action": "快速浏览弱信号列表，判断是否需要进一步跟踪。",
                        "related_topics": weak_signal_cluster.keywords,
                    }
                )
                titles_added.add(title)

        expansion = self._build_interest_expansion(emerging, user_profile)
        for suggestion in expansion:
            if suggestion["title"] not in titles_added:
                suggestions.append(suggestion)
                titles_added.add(suggestion["title"])

        return suggestions[: limit or len(suggestions)]

    def _build_interest_expansion(
        self,
        emerging_topics: List[Dict],
        user_profile: Optional[Dict],
        similarity_bounds: tuple = (0.55, 0.9),
    ) -> List[Dict]:
        if not user_profile:
            return []

        vector_profile = (user_profile.get("vector_profile") or {}).get(
            "implicit_interests_embedding"
        )
        if not vector_profile:
            return []

        user_vector = np.array(vector_profile, dtype=float)
        if user_vector.size == 0:
            return []
        norm = np.linalg.norm(user_vector)
        if norm == 0:
            return []
        user_vector = user_vector / norm

        suggestions: List[Dict] = []
        lower, upper = similarity_bounds

        for topic in emerging_topics:
            topic_text = " ; ".join(
                [topic.get("topic", "")] + (topic.get("keywords") or [])
            ).strip()
            if not topic_text:
                continue
            topic_vector = self._embedder.encode(
                topic_text,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            if topic_vector.ndim > 1:
                topic_vector = topic_vector[0]
            similarity = float(np.dot(user_vector, topic_vector))
            if similarity < lower or similarity > upper:
                continue

            suggestions.append(
                {
                    "title": f"扩展兴趣领域：{topic['topic']}",
                    "reason": f"与当前偏好相似度 {similarity:.2f}，但尚未成为核心关注。",
                    "action": "建议试读相关资料，并评估是否纳入长期跟踪。",
                    "related_topics": topic.get("keywords", []),
                }
            )

        return suggestions
