"""
相关性重排器 (Re-ranking)
基于用户画像向量和项目活跃度对内容进行重排
"""

import logging
from typing import List, Any, Dict, Optional
import numpy as np
from pathlib import Path

from src.memory.user_profile_manager import UserProfileManager

logger = logging.getLogger(__name__)


class ProjectActivityTracker:
    """
    项目活跃度追踪器
    
    追踪用户项目的活跃度（提交频率、讨论频率等）
    用于提升活跃项目的相关内容优先级
    """
    
    def __init__(self, profile_manager: Optional[UserProfileManager] = None):
        self.profile_manager = profile_manager
        self._activity_cache: Dict[str, float] = {}
    
    def get_project_activity(self, project_name: str) -> float:
        """
        获取项目活跃度分数 (0.0 - 1.0)
        
        Args:
            project_name: 项目名称
        
        Returns:
            活跃度分数（越高越活跃）
        """
        # 如果已缓存，直接返回
        if project_name in self._activity_cache:
            return self._activity_cache[project_name]
        
        # 默认活跃度（如果项目在用户配置中，给予基础分数）
        activity = 0.5  # 默认中等活跃度
        
        if self.profile_manager:
            profile = self.profile_manager.get_profile()
            active_projects = profile.get("active_projects", [])
            
            # 检查项目是否在活跃列表中
            for project in active_projects:
                if project.get("name") == project_name:
                    # 基础分数 + 根据项目状态调整
                    activity = 0.7
                    
                    # 如果有优先级标记，提升分数
                    if project.get("priority") == "high":
                        activity = 0.9
                    elif project.get("priority") == "medium":
                        activity = 0.7
                    elif project.get("priority") == "low":
                        activity = 0.5
                    
                    break
        
        # 缓存结果
        self._activity_cache[project_name] = activity
        
        return activity
    
    def update_activity(self, project_name: str, activity_score: float):
        """更新项目活跃度（可用于未来集成 Git API）"""
        self._activity_cache[project_name] = max(0.0, min(1.0, activity_score))


class ContentReranker:
    """
    内容重排器
    
    基于以下因素对内容进行重排：
    1. 用户画像向量相似度
    2. 项目活跃度
    3. 动态权重
    """
    
    def __init__(
        self,
        profile_manager: Optional[UserProfileManager] = None,
        activity_tracker: Optional[ProjectActivityTracker] = None,
        weight_adjuster: Optional[Any] = None,  # WeightAdjuster
    ):
        self.profile_manager = profile_manager
        self.activity_tracker = activity_tracker or ProjectActivityTracker(profile_manager)
        self.weight_adjuster = weight_adjuster
        
        # 权重系数
        self.similarity_weight = 0.4  # 向量相似度权重
        self.activity_weight = 0.3    # 项目活跃度权重
        self.base_score_weight = 0.3   # 基础分数权重
    
    def compute_similarity(self, item: Any, profile_vectors: Dict[str, np.ndarray]) -> float:
        """
        计算内容与用户画像的相似度
        
        Args:
            item: 内容项目
            profile_vectors: 用户画像向量字典
        
        Returns:
            相似度分数 (0.0 - 1.0)
        """
        if not profile_vectors:
            return 0.5  # 默认中等相似度
        
        # 提取内容文本
        content_text = self._extract_content_text(item)
        if not content_text:
            return 0.5
        
        # 计算内容向量（简化版：使用关键词匹配）
        # 实际应该使用 embedding 模型，但为了不依赖 SentenceTransformer，先用简化版
        similarity_scores = []
        
        # 1. 目标向量相似度
        if "goals_embedding" in profile_vectors:
            goal_sim = self._text_similarity_simple(
                content_text,
                profile_vectors.get("goals_text", ""),
            )
            similarity_scores.append(goal_sim * 0.3)
        
        # 2. 项目向量相似度
        if "projects_embedding" in profile_vectors:
            project_sim = self._text_similarity_simple(
                content_text,
                profile_vectors.get("projects_text", ""),
            )
            similarity_scores.append(project_sim * 0.4)
        
        # 3. 隐式兴趣向量相似度
        if "implicit_interests_embedding" in profile_vectors:
            implicit_sim = self._text_similarity_simple(
                content_text,
                profile_vectors.get("interests_text", ""),
            )
            similarity_scores.append(implicit_sim * 0.3)
        
        # 如果没有向量，使用默认值
        if not similarity_scores:
            return 0.5
        
        # 加权平均
        total_similarity = sum(similarity_scores)
        return min(1.0, max(0.0, total_similarity))
    
    def _extract_content_text(self, item: Any) -> str:
        """提取内容文本用于相似度计算"""
        parts = []
        
        # 标题
        title = getattr(item, 'title', '') or ''
        if title:
            parts.append(title)
        
        # 摘要
        summary = getattr(item, 'ai_summary', '') or getattr(item, 'summary', '') or ''
        if summary:
            parts.append(summary)
        
        # 为什么重要
        why_matters = getattr(item, 'why_matters_to_you', '') or ''
        if why_matters:
            parts.append(why_matters)
        
        return ' '.join(parts)
    
    def _text_similarity_simple(self, text1: str, text2: str) -> float:
        """
        简单的文本相似度计算（关键词匹配）
        
        注意：这是简化版，实际应该使用 embedding 向量相似度
        """
        if not text1 or not text2:
            return 0.5
        
        # 提取关键词（简单分词）
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.5
        
        # Jaccard 相似度
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        if union == 0:
            return 0.5
        
        similarity = intersection / union
        return similarity
    
    def compute_project_activity_score(self, item: Any) -> float:
        """
        计算项目活跃度分数
        
        Args:
            item: 内容项目
        
        Returns:
            活跃度分数 (0.0 - 1.0)
        """
        # 从项目关联中提取项目名称
        related_projects = getattr(item, 'related_projects', None)
        
        if not related_projects:
            return 0.5  # 默认中等活跃度
        
        # 如果是列表，取第一个项目
        if isinstance(related_projects, list):
            if not related_projects:
                return 0.5
            project_name = related_projects[0]
        else:
            project_name = str(related_projects)
        
        # 获取项目活跃度
        activity = self.activity_tracker.get_project_activity(project_name)
        
        return activity
    
    def rerank_items(
        self,
        items: List[Any],
        base_scores: Optional[List[float]] = None,
    ) -> List[Any]:
        """
        对内容列表进行重排
        
        Args:
            items: 内容项目列表
            base_scores: 基础分数列表（可选，默认使用 relevance_score）
        
        Returns:
            重排后的内容列表
        """
        if not items:
            return []
        
        # 获取用户画像向量（简化版）
        profile_vectors = self._get_profile_vectors()
        
        # 计算综合分数
        scored_items = []
        
        for i, item in enumerate(items):
            # 1. 基础分数
            if base_scores and i < len(base_scores):
                base_score = base_scores[i]
            else:
                base_score = getattr(item, 'relevance_score', 0) or 0
            
            # 2. 向量相似度
            similarity = self.compute_similarity(item, profile_vectors)
            
            # 3. 项目活跃度
            activity = self.compute_project_activity_score(item)
            
            # 4. 动态权重（如果可用）
            weight_multiplier = 1.0
            if self.weight_adjuster:
                source = getattr(item, 'source', '')
                category = getattr(item, 'category', '')
                source_weight = self.weight_adjuster.get_weight('sources', source)
                type_weight = self.weight_adjuster.get_weight('content_types', category)
                weight_multiplier = source_weight * type_weight
            
            # 5. 综合分数
            # 归一化基础分数到 0-1
            normalized_base = base_score / 10.0 if base_score > 0 else 0.5
            
            # 加权组合
            final_score = (
                normalized_base * self.base_score_weight +
                similarity * self.similarity_weight +
                activity * self.activity_weight
            ) * weight_multiplier
            
            scored_items.append((final_score, item))
        
        # 按分数排序
        scored_items.sort(key=lambda x: x[0], reverse=True)
        
        # 返回重排后的列表
        reranked = [item for _, item in scored_items]
        
        logger.info(
            f"✓ 重排完成: {len(items)} 条内容，"
            f"最高分: {scored_items[0][0]:.3f}, "
            f"最低分: {scored_items[-1][0]:.3f}"
        )
        
        return reranked
    
    def _get_profile_vectors(self) -> Dict[str, np.ndarray]:
        """获取用户画像向量（简化版，返回空字典表示未启用）"""
        if not self.profile_manager:
            return {}
        
        try:
            profile = self.profile_manager.get_profile()
            vector_profile = profile.get("vector_profile", {})
            
            # 转换为 numpy 数组
            vectors = {}
            for key in ["goals_embedding", "projects_embedding", "implicit_interests_embedding"]:
                if key in vector_profile:
                    vec = vector_profile[key]
                    if isinstance(vec, list):
                        vectors[key] = np.array(vec)
            
            # 提取文本用于简化相似度计算
            # 实际应该使用 embedding，但为了简化，先提取文本
            goals_text = ' '.join(self.profile_manager._collect_goal_text())
            projects_text = ' '.join(self.profile_manager._collect_project_text())
            
            vectors["goals_text"] = goals_text
            vectors["projects_text"] = projects_text
            vectors["interests_text"] = goals_text + ' ' + projects_text
            
            return vectors
        except Exception as e:
            logger.warning(f"获取用户画像向量失败: {e}")
            return {}


def rerank_must_read_items(
    items: List[Any],
    profile_manager: Optional[UserProfileManager] = None,
    weight_adjuster: Optional[Any] = None,
) -> List[Any]:
    """
    重排"必看内容"列表
    
    便捷函数，用于报告生成器集成
    """
    reranker = ContentReranker(
        profile_manager=profile_manager,
        weight_adjuster=weight_adjuster,
    )
    
    return reranker.rerank_items(items)


__all__ = ["ContentReranker", "ProjectActivityTracker", "rerank_must_read_items"]

