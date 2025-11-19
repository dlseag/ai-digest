"""
测试个性化权重自动调整器
"""

import pytest
import json
from pathlib import Path
from datetime import datetime
from src.learning.weight_adjuster import WeightAdjuster
from src.storage.feedback_db import FeedbackDB


class TestWeightAdjuster:
    """测试权重调整器"""
    
    @pytest.fixture
    def temp_db(self, tmp_path):
        """创建临时数据库"""
        db_path = tmp_path / "test_feedback.db"
        db = FeedbackDB(db_path=db_path)
        yield db
        if db_path.exists():
            db_path.unlink()
    
    @pytest.fixture
    def temp_config(self, tmp_path):
        """创建临时配置文件路径"""
        config_path = tmp_path / "test_weights.json"
        yield config_path
        if config_path.exists():
            config_path.unlink()
    
    @pytest.fixture
    def adjuster(self, temp_db, temp_config):
        """创建权重调整器实例"""
        return WeightAdjuster(db=temp_db, config_path=temp_config, alpha=0.3)
    
    def test_initialization(self, adjuster):
        """测试初始化"""
        weights = adjuster.get_all_weights()
        
        # 验证默认权重结构
        assert "content_types" in weights
        assert "sources" in weights
        assert "sections" in weights
        assert "last_updated" in weights
        
        # 验证默认内容类型权重
        assert weights["content_types"]["paper"] == 1.0
        assert weights["content_types"]["article"] == 1.0
    
    def test_get_weight_default(self, adjuster):
        """测试获取不存在的权重返回默认值"""
        weight = adjuster.get_weight("sources", "unknown_source")
        assert weight == 1.0
    
    def test_compute_adjustments_no_data(self, adjuster):
        """测试无数据时的调整"""
        result = adjuster.compute_adjustments(days=7)
        
        assert "adjustments" in result
        assert len(result["adjustments"]) == 0
        assert result.get("message") == "暂无数据"
    
    def test_compute_adjustments_with_like_feedback(self, temp_db, adjuster):
        """测试基于点赞反馈的权重调整"""
        # 创建 10 条点赞的 must_read 反馈
        for i in range(10):
            behavior = {
                "report_id": "2025-11-12",
                "item_id": f"item_{i}",
                "action": "feedback",
                "feedback_type": "like",
                "section": "must_read",
                "metadata": json.dumps({"source": "arXiv"})
            }
            temp_db.save_reading_behavior(behavior)
        
        # 计算调整
        result = adjuster.compute_adjustments(days=7)
        
        # 验证有调整
        assert len(result["adjustments"]) > 0
        
        # 验证 must_read 权重上升
        section_adjustments = [
            adj for adj in result["adjustments"] 
            if adj["type"] == "section" and adj["target"] == "must_read"
        ]
        
        assert len(section_adjustments) > 0
        adj = section_adjustments[0]
        assert adj["new_weight"] > adj["old_weight"]  # 权重应该增加
    
    def test_compute_adjustments_with_dislike_feedback(self, temp_db, adjuster):
        """测试基于踩反馈的权重调整"""
        # 创建 10 条踩的 headlines 反馈
        for i in range(10):
            behavior = {
                "report_id": "2025-11-12",
                "item_id": f"item_{i}",
                "action": "feedback",
                "feedback_type": "dislike",
                "section": "headlines",
                "metadata": json.dumps({"source": "Reddit"})
            }
            temp_db.save_reading_behavior(behavior)
        
        # 计算调整
        result = adjuster.compute_adjustments(days=7)
        
        # 验证 headlines 权重下降
        section_adjustments = [
            adj for adj in result["adjustments"] 
            if adj["type"] == "section" and adj["target"] == "headlines"
        ]
        
        if section_adjustments:
            adj = section_adjustments[0]
            assert adj["new_weight"] < adj["old_weight"]  # 权重应该降低
    
    def test_ema_smoothing(self, temp_db, adjuster):
        """测试 EMA 平滑效果"""
        # 创建大量点赞反馈
        for i in range(20):
            behavior = {
                "report_id": "2025-11-12",
                "item_id": f"item_{i}",
                "action": "feedback",
                "feedback_type": "like",
                "section": "must_read",
                "metadata": json.dumps({"source": "arXiv"})
            }
            temp_db.save_reading_behavior(behavior)
        
        # 第一次调整
        result1 = adjuster.compute_adjustments(days=7)
        old_weight_1 = adjuster.get_weight("sections", "must_read")
        
        # 再添加更多点赞
        for i in range(20, 40):
            behavior = {
                "report_id": "2025-11-13",
                "item_id": f"item_{i}",
                "action": "feedback",
                "feedback_type": "like",
                "section": "must_read",
                "metadata": json.dumps({"source": "arXiv"})
            }
            temp_db.save_reading_behavior(behavior)
        
        # 第二次调整
        result2 = adjuster.compute_adjustments(days=7)
        new_weight_2 = adjuster.get_weight("sections", "must_read")
        
        # 验证权重逐步增加（EMA 平滑）
        assert new_weight_2 >= old_weight_1  # 权重应该继续增加或保持
    
    def test_minimum_feedback_threshold(self, temp_db, adjuster):
        """测试最小反馈阈值"""
        # 只创建 2 条反馈（少于阈值 3）
        for i in range(2):
            behavior = {
                "report_id": "2025-11-12",
                "item_id": f"item_{i}",
                "action": "feedback",
                "feedback_type": "like",
                "section": "test_section",
                "metadata": json.dumps({"source": "Test"})
            }
            temp_db.save_reading_behavior(behavior)
        
        # 计算调整
        result = adjuster.compute_adjustments(days=7)
        
        # 验证没有调整（反馈数不足）
        section_adjustments = [
            adj for adj in result["adjustments"] 
            if adj["type"] == "section" and adj["target"] == "test_section"
        ]
        
        assert len(section_adjustments) == 0
    
    def test_source_weight_adjustment(self, temp_db, adjuster):
        """测试来源权重调整"""
        # 创建足够的反馈（至少 5 条）
        for i in range(10):
            behavior = {
                "report_id": "2025-11-12",
                "item_id": f"item_{i}",
                "action": "feedback",
                "feedback_type": "like",
                "section": "must_read",
                "metadata": json.dumps({"source": "Papers with Code"})
            }
            temp_db.save_reading_behavior(behavior)
        
        # 计算调整
        result = adjuster.compute_adjustments(days=7)
        
        # 验证来源权重调整
        source_adjustments = [
            adj for adj in result["adjustments"] 
            if adj["type"] == "source" and adj["target"] == "Papers with Code"
        ]
        
        if source_adjustments:
            adj = source_adjustments[0]
            assert adj["new_weight"] > adj["old_weight"]
            assert adj["feedback_count"] >= 5
    
    def test_adjustments_history(self, temp_db, adjuster):
        """测试调整历史记录"""
        # 创建反馈
        for i in range(10):
            behavior = {
                "report_id": "2025-11-12",
                "item_id": f"item_{i}",
                "action": "feedback",
                "feedback_type": "like",
                "section": "must_read",
            }
            temp_db.save_reading_behavior(behavior)
        
        # 计算调整
        adjuster.compute_adjustments(days=7)
        
        # 验证历史记录
        weights = adjuster.get_all_weights()
        assert "adjustments_history" in weights
        assert len(weights["adjustments_history"]) > 0
        
        # 验证历史记录结构
        history_item = weights["adjustments_history"][-1]
        assert "timestamp" in history_item
        assert "adjustments" in history_item
        assert "data_window_days" in history_item
    
    def test_save_and_load_weights(self, adjuster, temp_config):
        """测试权重保存和加载"""
        # 修改权重
        adjuster.weights["sections"]["test_section"] = 1.5
        adjuster._save_weights()
        
        # 验证文件存在
        assert temp_config.exists()
        
        # 重新加载
        new_adjuster = WeightAdjuster(config_path=temp_config)
        loaded_weight = new_adjuster.get_weight("sections", "test_section")
        
        assert loaded_weight == 1.5
    
    def test_reset_weights(self, adjuster):
        """测试重置权重"""
        # 修改权重
        adjuster.weights["sections"]["test_section"] = 2.0
        
        # 重置
        adjuster.reset_weights()
        
        # 验证权重恢复默认
        weight = adjuster.get_weight("sections", "test_section")
        assert weight == 1.0  # 默认值
        
        # 验证重置记录
        weights = adjuster.get_all_weights()
        history = weights["adjustments_history"]
        assert any(h.get("action") == "reset" for h in history)
    
    def test_weight_bounds(self, temp_db, adjuster):
        """测试权重边界限制"""
        # 创建极端反馈（全部点赞）
        for i in range(100):
            behavior = {
                "report_id": "2025-11-12",
                "item_id": f"item_{i}",
                "action": "feedback",
                "feedback_type": "like",
                "section": "must_read",
            }
            temp_db.save_reading_behavior(behavior)
        
        # 多次调整
        for _ in range(5):
            adjuster.compute_adjustments(days=7)
        
        # 验证权重不超过上限
        weight = adjuster.get_weight("sections", "must_read")
        assert weight <= 2.0  # 上限
        
        # 创建极端反馈（全部踩）
        for i in range(100):
            behavior = {
                "report_id": "2025-11-13",
                "item_id": f"item_{i}",
                "action": "feedback",
                "feedback_type": "dislike",
                "section": "test_low",
            }
            temp_db.save_reading_behavior(behavior)
        
        # 调整
        for _ in range(5):
            adjuster.compute_adjustments(days=7)
        
        # 验证权重不低于下限
        weight = adjuster.get_weight("sections", "test_low")
        assert weight >= 0.2  # 下限（来源）或 0.3（区域）


class TestWeightApplication:
    """测试权重应用"""
    
    @pytest.fixture
    def adjuster(self, tmp_path):
        """创建带预设权重的调整器"""
        config_path = tmp_path / "test_weights.json"
        adjuster = WeightAdjuster(config_path=config_path)
        
        # 设置测试权重
        adjuster.weights["sources"]["arXiv"] = 1.5
        adjuster.weights["sources"]["Reddit"] = 0.7
        adjuster.weights["content_types"]["paper"] = 1.2
        adjuster.weights["content_types"]["article"] = 0.9
        
        return adjuster
    
    def test_get_combined_weight(self, adjuster):
        """测试获取组合权重"""
        # arXiv paper: 1.5 * 1.2 = 1.8
        arxiv_weight = adjuster.get_weight("sources", "arXiv")
        paper_weight = adjuster.get_weight("content_types", "paper")
        combined = arxiv_weight * paper_weight
        
        assert combined == pytest.approx(1.8, rel=0.01)
        
        # Reddit article: 0.7 * 0.9 = 0.63
        reddit_weight = adjuster.get_weight("sources", "Reddit")
        article_weight = adjuster.get_weight("content_types", "article")
        combined = reddit_weight * article_weight
        
        assert combined == pytest.approx(0.63, rel=0.01)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
