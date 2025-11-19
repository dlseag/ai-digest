"""
测试相关性重排器 (Re-ranking)
"""

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock
from src.learning.reranker import ContentReranker, ProjectActivityTracker
from src.memory.user_profile_manager import UserProfileManager


class MockItem:
    """模拟内容项目"""
    def __init__(self, title, summary="", relevance_score=7.0, related_projects=None, source="", category="article", why_matters_to_you=""):
        self.title = title
        self.summary = summary
        self.ai_summary = summary
        self.relevance_score = relevance_score
        self.related_projects = related_projects or []
        self.source = source
        self.category = category
        self.why_matters_to_you = why_matters_to_you


class TestProjectActivityTracker:
    """测试项目活跃度追踪器"""
    
    @pytest.fixture
    def mock_profile_manager(self):
        """创建模拟的用户画像管理器"""
        manager = Mock(spec=UserProfileManager)
        manager.get_profile.return_value = {
            "active_projects": [
                {"name": "mutation-test-killer", "priority": "high"},
                {"name": "ai-digest", "priority": "medium"},
                {"name": "rag-practics", "priority": "low"},
            ]
        }
        return manager
    
    def test_get_project_activity_high_priority(self, mock_profile_manager):
        """测试高优先级项目活跃度"""
        tracker = ProjectActivityTracker(profile_manager=mock_profile_manager)
        
        activity = tracker.get_project_activity("mutation-test-killer")
        
        assert activity == 0.9  # 高优先级
    
    def test_get_project_activity_medium_priority(self, mock_profile_manager):
        """测试中等优先级项目活跃度"""
        tracker = ProjectActivityTracker(profile_manager=mock_profile_manager)
        
        activity = tracker.get_project_activity("ai-digest")
        
        assert activity == 0.7  # 中等优先级
    
    def test_get_project_activity_low_priority(self, mock_profile_manager):
        """测试低优先级项目活跃度"""
        tracker = ProjectActivityTracker(profile_manager=mock_profile_manager)
        
        activity = tracker.get_project_activity("rag-practics")
        
        assert activity == 0.5  # 低优先级
    
    def test_get_project_activity_unknown(self):
        """测试未知项目活跃度（默认值）"""
        tracker = ProjectActivityTracker()
        
        activity = tracker.get_project_activity("unknown-project")
        
        assert activity == 0.5  # 默认中等活跃度
    
    def test_update_activity(self):
        """测试更新项目活跃度"""
        tracker = ProjectActivityTracker()
        
        tracker.update_activity("test-project", 0.8)
        activity = tracker.get_project_activity("test-project")
        
        assert activity == 0.8
    
    def test_activity_bounds(self):
        """测试活跃度边界限制"""
        tracker = ProjectActivityTracker()
        
        # 测试上限
        tracker.update_activity("high", 1.5)
        assert tracker.get_project_activity("high") == 1.0
        
        # 测试下限
        tracker.update_activity("low", -0.5)
        assert tracker.get_project_activity("low") == 0.0


class TestContentReranker:
    """测试内容重排器"""
    
    @pytest.fixture
    def mock_profile_manager(self):
        """创建模拟的用户画像管理器"""
        manager = Mock(spec=UserProfileManager)
        manager.get_profile.return_value = {
            "vector_profile": {
                "goals_embedding": [0.1] * 384,
                "projects_embedding": [0.2] * 384,
                "implicit_interests_embedding": [0.15] * 384,
            },
            "active_projects": [
                {"name": "mutation-test-killer", "priority": "high"},
            ]
        }
        manager._collect_goal_text.return_value = ["test goals", "machine learning"]
        manager._collect_project_text.return_value = ["mutation testing", "test generation"]
        return manager
    
    @pytest.fixture
    def mock_weight_adjuster(self):
        """创建模拟的权重调整器"""
        adjuster = Mock()
        adjuster.get_weight.side_effect = lambda dim, key: {
            ("sources", "arXiv"): 1.2,
            ("sources", "Papers with Code"): 1.0,
            ("content_types", "paper"): 1.1,
            ("content_types", "article"): 1.0,
        }.get((dim, key), 1.0)
        return adjuster
    
    def test_rerank_items_basic(self):
        """测试基本重排功能"""
        reranker = ContentReranker()
        
        items = [
            MockItem("Item A", relevance_score=8.0),
            MockItem("Item B", relevance_score=7.0),
            MockItem("Item C", relevance_score=9.0),
        ]
        
        reranked = reranker.rerank_items(items)
        
        # 验证重排后顺序（应该按分数降序）
        assert len(reranked) == 3
        assert reranked[0].title == "Item C"  # 最高分
    
    def test_rerank_items_with_custom_scores(self):
        """测试使用自定义基础分数"""
        reranker = ContentReranker()
        
        items = [
            MockItem("Item A"),
            MockItem("Item B"),
            MockItem("Item C"),
        ]
        
        base_scores = [9.0, 7.0, 8.0]
        
        reranked = reranker.rerank_items(items, base_scores=base_scores)
        
        # 验证重排后顺序
        assert reranked[0].title == "Item A"  # 最高分 9.0
    
    def test_rerank_items_with_project_activity(self, mock_profile_manager):
        """测试项目活跃度影响重排"""
        reranker = ContentReranker(profile_manager=mock_profile_manager)
        
        items = [
            MockItem("Item A", relevance_score=7.0, related_projects=["mutation-test-killer"]),
            MockItem("Item B", relevance_score=7.0, related_projects=["unknown-project"]),
        ]
        
        reranked = reranker.rerank_items(items)
        
        # 验证活跃项目相关的内容排在前面
        assert reranked[0].related_projects == ["mutation-test-killer"]
    
    def test_rerank_items_with_weight_adjuster(self, mock_weight_adjuster):
        """测试权重调整器影响重排"""
        reranker = ContentReranker(weight_adjuster=mock_weight_adjuster)
        
        items = [
            MockItem("Item A", relevance_score=7.0, source="arXiv", category="paper"),
            MockItem("Item B", relevance_score=7.0, source="Papers with Code", category="article"),
        ]
        
        reranked = reranker.rerank_items(items)
        
        # 验证高权重来源的内容排在前面
        # arXiv (1.2) * paper (1.1) = 1.32 > Papers with Code (1.0) * article (1.0) = 1.0
        assert reranked[0].source == "arXiv"
    
    def test_compute_similarity(self, mock_profile_manager):
        """测试相似度计算"""
        reranker = ContentReranker(profile_manager=mock_profile_manager)
        
        # 创建与用户目标相关的内容
        item = MockItem(
            title="Machine Learning Research",
            summary="This is about machine learning and test generation",
        )
        
        profile_vectors = {
            "goals_text": "test goals machine learning",
            "projects_text": "mutation testing test generation",
            "interests_text": "test goals machine learning mutation testing test generation",
        }
        
        similarity = reranker.compute_similarity(item, profile_vectors)
        
        # 验证相似度在合理范围
        assert 0.0 <= similarity <= 1.0
    
    def test_compute_similarity_no_vectors(self):
        """测试无向量时的相似度计算"""
        reranker = ContentReranker()
        
        item = MockItem(title="Test Item")
        
        similarity = reranker.compute_similarity(item, {})
        
        # 应该返回默认值
        assert similarity == 0.5
    
    def test_compute_project_activity_score(self, mock_profile_manager):
        """测试项目活跃度分数计算"""
        reranker = ContentReranker(profile_manager=mock_profile_manager)
        
        item = MockItem(
            title="Test Item",
            related_projects=["mutation-test-killer"],
        )
        
        activity = reranker.compute_project_activity_score(item)
        
        # 验证活跃度分数
        assert 0.0 <= activity <= 1.0
        assert activity == 0.9  # 高优先级项目
    
    def test_compute_project_activity_score_no_projects(self):
        """测试无项目关联时的活跃度分数"""
        reranker = ContentReranker()
        
        item = MockItem(title="Test Item", related_projects=[])
        
        activity = reranker.compute_project_activity_score(item)
        
        # 应该返回默认值
        assert activity == 0.5
    
    def test_extract_content_text(self):
        """测试内容文本提取"""
        reranker = ContentReranker()
        
        item = MockItem(
            title="Test Title",
            summary="Test Summary",
            why_matters_to_you="Why it matters",
        )
        
        text = reranker._extract_content_text(item)
        
        assert "Test Title" in text
        assert "Test Summary" in text
        assert "Why it matters" in text
    
    def test_text_similarity_simple(self):
        """测试简单文本相似度计算"""
        reranker = ContentReranker()
        
        similarity = reranker._text_similarity_simple(
            "machine learning test generation",
            "machine learning testing",
        )
        
        # 验证相似度在合理范围
        assert 0.0 <= similarity <= 1.0
        assert similarity > 0.3  # 有共同词
    
    def test_text_similarity_simple_no_overlap(self):
        """测试无重叠文本的相似度"""
        reranker = ContentReranker()
        
        similarity = reranker._text_similarity_simple(
            "apple banana",
            "orange grape",
        )
        
        # 应该返回较低相似度
        assert similarity < 0.5
    
    def test_rerank_empty_list(self):
        """测试空列表重排"""
        reranker = ContentReranker()
        
        reranked = reranker.rerank_items([])
        
        assert reranked == []
    
    def test_rerank_single_item(self):
        """测试单个项目重排"""
        reranker = ContentReranker()
        
        items = [MockItem("Single Item", relevance_score=8.0)]
        
        reranked = reranker.rerank_items(items)
        
        assert len(reranked) == 1
        assert reranked[0].title == "Single Item"


class TestRerankerIntegration:
    """测试重排器集成场景"""
    
    def test_rerank_with_all_factors(self):
        """测试综合所有因素的重排"""
        # 创建模拟组件
        profile_manager = Mock(spec=UserProfileManager)
        profile_manager.get_profile.return_value = {
            "vector_profile": {},
            "active_projects": [
                {"name": "project-A", "priority": "high"},
            ]
        }
        profile_manager._collect_goal_text.return_value = ["goal A"]
        profile_manager._collect_project_text.return_value = ["project A"]
        
        weight_adjuster = Mock()
        weight_adjuster.get_weight.return_value = 1.0
        
        reranker = ContentReranker(
            profile_manager=profile_manager,
            weight_adjuster=weight_adjuster,
        )
        
        # 创建测试项目
        items = [
            MockItem(
                "Item 1",
                relevance_score=8.0,
                related_projects=["project-A"],
                source="Source A",
            ),
            MockItem(
                "Item 2",
                relevance_score=9.0,
                related_projects=[],
                source="Source B",
            ),
        ]
        
        reranked = reranker.rerank_items(items)
        
        # 验证重排成功
        assert len(reranked) == 2
        # Item 1 应该排在前面（因为项目活跃度高）
        assert reranked[0].related_projects == ["project-A"]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

