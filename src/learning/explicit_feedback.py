"""Explicit feedback manager for storing and retrieving few-shot corrections."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np
# 禁用导入，避免触发 transformers 锁问题
# from sentence_transformers import SentenceTransformer
SentenceTransformer = None

from src.storage.feedback_db import FeedbackDB

DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"


@dataclass
class FewShotExample:
    """A normalized few-shot correction example."""

    original_output: str
    corrected_output: str
    article_context: str
    created_at: str
    score: float


class ExplicitFeedbackManager:
    """Handles persistence and retrieval of explicit user corrections."""

    def __init__(
        self,
        db: FeedbackDB,
        *,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        self.db = db
        # 延迟初始化嵌入模型
        self._embedder = None
        self._embedding_model = embedding_model
        self._embedding_failed = False

    def _ensure_embedder(self) -> bool:
        """延迟加载嵌入模型"""
        if self._embedder:
            return True
        if self._embedding_failed or SentenceTransformer is None:
            return False
        
        try:
            self._embedder = SentenceTransformer(self._embedding_model)
            return True
        except Exception:
            self._embedding_failed = True
            return False

    # ------------------------------------------------------------------
    # Recording corrections
    # ------------------------------------------------------------------
    def record_correction(
        self,
        *,
        original_output: str,
        corrected_output: str,
        article_context: str,
        correction_type: str = "analysis",
    ) -> None:
        embedding = self._encode(article_context)
        self.db.save_few_shot_correction(
            {
                "correction_type": correction_type,
                "original_output": original_output,
                "corrected_output": corrected_output,
                "article_context": article_context,
                "article_embedding": embedding.tolist(),
            }
        )

    # ------------------------------------------------------------------
    # Retrieval helpers
    # ------------------------------------------------------------------
    def retrieve_similar_corrections(
        self,
        article_text: str,
        *,
        correction_type: str = "analysis",
        top_k: int = 3,
        min_score: float = 0.2,
    ) -> List[FewShotExample]:
        base_embedding = self._encode(article_text)
        candidates = self.db.fetch_few_shot_corrections(correction_type, limit=100)

        scored: List[FewShotExample] = []
        for candidate in candidates:
            embedding = np.array(candidate.get("article_embedding") or [])
            if embedding.size == 0:
                continue
            score = float(np.dot(base_embedding, embedding))
            if score < min_score:
                continue
            scored.append(
                FewShotExample(
                    original_output=candidate.get("original_output", ""),
                    corrected_output=candidate.get("corrected_output", ""),
                    article_context=candidate.get("article_context", ""),
                    created_at=candidate.get("created_at", ""),
                    score=score,
                )
            )

        scored.sort(key=lambda example: example.score, reverse=True)
        return scored[:top_k]

    def get_recent_corrections(
        self,
        *,
        correction_type: str = "analysis",
        top_k: int = 3,
    ) -> List[FewShotExample]:
        candidates = self.db.fetch_few_shot_corrections(correction_type, limit=top_k)
        examples: List[FewShotExample] = []
        for candidate in candidates:
            examples.append(
                FewShotExample(
                    original_output=candidate.get("original_output", ""),
                    corrected_output=candidate.get("corrected_output", ""),
                    article_context=candidate.get("article_context", ""),
                    created_at=candidate.get("created_at", ""),
                    score=0.0,
                )
            )
        return examples

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _encode(self, text: str) -> np.ndarray:
        if not self._ensure_embedder():
            return np.zeros(384)  # 返回零向量作为fallback
        embedding = self._embedder.encode(
            text or "",
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        if embedding.ndim > 1:
            embedding = embedding[0]
        return embedding


__all__ = ["ExplicitFeedbackManager", "FewShotExample"]
