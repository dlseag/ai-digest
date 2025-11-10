"""User profile manager with multi-vector embeddings and EMA updates."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np

# 完全禁用 SentenceTransformer 导入，避免锁问题
# 即使导入类本身也会触发 transformers 库的缓存访问
SentenceTransformer = None


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_VECTORS_PATH = PROJECT_ROOT / "data" / "user_profile_vectors.json"
DEFAULT_FACTS_PATH = PROJECT_ROOT / "data" / "user_profile_facts.json"


class UserProfileManager:
    """Loads the user profile and maintains embedding vectors."""

    def __init__(
        self,
        profile_path: Path,
        profile_data: Optional[Dict] = None,
        *,
        vectors_path: Optional[Path] = None,
        embedding_model: str = DEFAULT_EMBEDDING_MODEL,
    ) -> None:
        self.profile_path = Path(profile_path)
        self.vectors_path = Path(vectors_path or DEFAULT_VECTORS_PATH)
        self.facts_path = DEFAULT_FACTS_PATH
        self.vectors_path.parent.mkdir(parents=True, exist_ok=True)
        self.facts_path.parent.mkdir(parents=True, exist_ok=True)

        self._profile = profile_data or self._load_profile()
        
        # 延迟加载嵌入模型（仅在需要时加载）
        self._embedder = None
        self._embedding_model = embedding_model
        self._embedding_failed = False
        
        self._vectors = self._load_vectors()
        self._facts = self._load_facts()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_profile(self) -> Dict:
        """Return profile dict including vector profile."""

        profile_copy = deepcopy(self._profile)
        profile_copy.setdefault("vector_profile", deepcopy(self._vectors))
        profile_copy.setdefault("preference_facts", list(self._facts))
        return profile_copy

    def update_implicit_vector(self, text: str, *, positive: bool = True, learning_rate: float = 0.05) -> None:
        """Apply EMA update to the implicit interests embedding."""
        
        if not self._embedder:
            return  # 嵌入功能未启用

        text = (text or "").strip()
        if not text:
            return

        embedding = self._encode_text(text)
        current = np.array(self._vectors.get("implicit_interests_embedding"))
        if current.size == 0:
            current = embedding

        if positive:
            updated = (current * (1 - learning_rate)) + (embedding * learning_rate)
        else:
            # Push the representation away slightly for negative feedback.
            updated = (current * (1 + learning_rate)) - (embedding * learning_rate)

        norm = np.linalg.norm(updated)
        if norm > 0:
            updated = updated / norm

        updated_list = updated.tolist()
        self._vectors["implicit_interests_embedding"] = updated_list
        self._profile.setdefault("vector_profile", {})["implicit_interests_embedding"] = deepcopy(updated_list)
        self._profile.setdefault("preference_facts", list(self._facts))

    def save_vectors(self) -> None:
        with self.vectors_path.open("w", encoding="utf-8") as handle:
            json.dump(self._vectors, handle, ensure_ascii=False, indent=2)

    def add_preference_facts(self, facts: List[str]) -> None:
        if not facts:
            return
        added = False
        for fact in facts:
            fact = fact.strip()
            if fact and fact not in self._facts:
                self._facts.append(fact)
                added = True
        if added:
            self.save_facts()

    def save_facts(self) -> None:
        with self.facts_path.open("w", encoding="utf-8") as handle:
            json.dump(self._facts, handle, ensure_ascii=False, indent=2)
        self._profile.setdefault("preference_facts", list(self._facts))

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def ensure_vector_profile(self) -> None:
        """Ensure goals/projects/implicit embeddings exist."""

        goals_embedding = self._vectors.get("goals_embedding")
        projects_embedding = self._vectors.get("projects_embedding")
        implicit_embedding = self._vectors.get("implicit_interests_embedding")

        if goals_embedding is None:
            goals_text = self._collect_goal_text()
            goals_embedding = self._average_embeddings(goals_text)
            self._vectors["goals_embedding"] = goals_embedding.tolist()

        if projects_embedding is None:
            project_text = self._collect_project_text()
            projects_embedding = self._average_embeddings(project_text)
            self._vectors["projects_embedding"] = projects_embedding.tolist()

        if implicit_embedding is None:
            base = self._average_embeddings(
                self._collect_goal_text() + self._collect_project_text()
            )
            self._vectors["implicit_interests_embedding"] = base.tolist()

        profile_vector = deepcopy(self._vectors)
        self._profile.setdefault("vector_profile", profile_vector)

    def _load_profile(self) -> Dict:
        if not self.profile_path.exists():
            raise FileNotFoundError(f"User profile not found: {self.profile_path}")
        if self.profile_path.suffix.lower() in {".json"}:
            with self.profile_path.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        return self._load_yaml()

    def _load_yaml(self) -> Dict:
        import yaml  # Lazy import to avoid mandatory dependency at module load

        with self.profile_path.open("r", encoding="utf-8") as handle:
            return yaml.safe_load(handle) or {}

    def _load_vectors(self) -> Dict:
        if not self.vectors_path.exists():
            return {}
        try:
            with self.vectors_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
                # Normalise to list type
                for key, value in list(data.items()):
                    if isinstance(value, list):
                        data[key] = value
                return data
        except json.JSONDecodeError:
            return {}

    def _collect_goal_text(self) -> List[str]:
        goals = []
        career_goals = self._profile.get("career_goals", {})
        if isinstance(career_goals, dict):
            primary = career_goals.get("primary")
            if primary:
                goals.append(str(primary))
            secondary = career_goals.get("secondary", [])
            if isinstance(secondary, list):
                goals.extend(str(item) for item in secondary if item)
            long_term = career_goals.get("long_term_vision")
            if long_term:
                goals.append(str(long_term))
        goals.extend(self._profile.get("learning_focus", {}).get("current", []))
        return [g for g in goals if g]

    def _collect_project_text(self) -> List[str]:
        projects = []
        for project in self._profile.get("active_projects", []) or []:
            name = project.get("name")
            description = project.get("description")
            goals = project.get("goals", [])
            parts = [name or "", description or ""] + [str(goal) for goal in goals]
            projects.append(" \n ".join(part for part in parts if part))
        return [p for p in projects if p]

    def _average_embeddings(self, texts: List[str]) -> np.ndarray:
        if not texts:
            return np.zeros(self._embedder.get_sentence_embedding_dimension())
        embeddings = self._embedder.encode(
            texts,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        if embeddings.ndim == 1:
            return embeddings
        vector = embeddings.mean(axis=0)
        norm = np.linalg.norm(vector)
        return vector / norm if norm > 0 else vector

    def _ensure_embedder(self) -> bool:
        """延迟加载嵌入模型"""
        if self._embedder:
            return True
        if self._embedding_failed:
            return False
        
        # 检查是否设置了离线模式
        import os
        if os.getenv('TRANSFORMERS_OFFLINE') == '1' or os.getenv('HF_HUB_OFFLINE') == '1':
            print("检测到离线模式，跳过嵌入模型加载")
            self._embedding_failed = True
            return False
        
        if SentenceTransformer is None:
            print("SentenceTransformer 未加载（离线模式或未安装）")
            self._embedding_failed = True
            return False
        
        try:
            print(f"正在加载嵌入模型: {self._embedding_model}...")
            self._embedder = SentenceTransformer(self._embedding_model)
            print("✓ 嵌入模型加载成功")
            return True
        except Exception as e:
            print(f"警告：无法加载嵌入模型: {e}")
            print("提示：向量嵌入功能将被禁用")
            self._embedding_failed = True
            return False
    
    def _encode_text(self, text: str) -> np.ndarray:
        if not self._ensure_embedder():
            return np.zeros(384)  # 返回零向量作为fallback
        embedding = self._embedder.encode(
            text,
            convert_to_numpy=True,
            normalize_embeddings=True,
        )
        if embedding.ndim > 1:
            embedding = embedding[0]
        return embedding

    def _load_facts(self) -> List[str]:
        if not self.facts_path.exists():
            return []
        try:
            with self.facts_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
                if isinstance(data, list):
                    return [str(item) for item in data if item]
        except json.JSONDecodeError:
            return []
        return []


__all__ = ["UserProfileManager"]
