"""
测试反馈闭环优化器
"""

import pytest
import json
from pathlib import Path
from src.learning.feedback_reinforcer import FeedbackReinforcer
from src.storage.feedback_db import FeedbackDB
from src.learning.weight_adjuster import WeightAdjuster


class TestFeedbackReinforcer:
    """测试反馈强化器"""
    
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
    def reinforcer(self, temp_db, temp_config):
        """创建反馈强化器实例"""
        weight_adjuster = WeightAdjuster(config_path=temp_config)
        return FeedbackReinforcer(db=temp_db, weight_adjuster=weight_adjuster)
    
    def test_record_action_feedback_execute(self, reinforcer):
        """测试记录执行反馈"""
        reinforcer.record_action_feedback(
            action_id="test_action_123",
            action_type="reading_list",
            feedback_type="execute",
            tool_name="add_to_reading_list",
            success=True,
        )
        
        # 验证已记录
        behaviors = reinforcer.db.get_behaviors(item_id="test_action_123", days=7)
        assert len(behaviors) == 1
        assert "action_feedback_execute" in behaviors[0]["action"]
    
    def test_record_action_feedback_skip(self, reinforcer):
        """测试记录跳过反馈"""
        reinforcer.record_action_feedback(
            action_id="test_action_456",
            action_type="github_issue",
            feedback_type="skip",
        )
        
        # 验证已记录
        behaviors = reinforcer.db.get_behaviors(item_id="test_action_456", days=7)
        assert len(behaviors) == 1
    
    def test_record_action_feedback_irrelevant(self, reinforcer):
        """测试记录不相关反馈"""
        reinforcer.record_action_feedback(
            action_id="test_action_789",
            action_type="calendar",
            feedback_type="irrelevant",
        )
        
        # 验证已记录
        behaviors = reinforcer.db.get_behaviors(item_id="test_action_789", days=7)
        assert len(behaviors) == 1
    
    def test_reinforce_action_weight(self, reinforcer):
        """测试强化行动权重"""
        # 初始权重
        initial_weight = reinforcer.get_action_type_weight("reading_list")
        assert initial_weight == 1.0
        
        # 记录成功执行
        reinforcer.record_action_feedback(
            action_id="test_action",
            action_type="reading_list",
            feedback_type="execute",
            success=True,
        )
        
        # 验证权重增加
        new_weight = reinforcer.get_action_type_weight("reading_list")
        assert new_weight > initial_weight
        assert new_weight <= 2.0  # 上限
    
    def test_reinforce_weight_multiple_times(self, reinforcer):
        """测试多次强化权重"""
        # 多次成功执行
        for i in range(5):
            reinforcer.record_action_feedback(
                action_id=f"test_action_{i}",
                action_type="github_issue",
                feedback_type="execute",
                success=True,
            )
        
        # 验证权重逐步增加
        weight = reinforcer.get_action_type_weight("github_issue")
        assert weight > 1.0
        assert weight <= 2.0
    
    def test_calculate_learning_metrics(self, reinforcer):
        """测试计算学习指标"""
        # 创建测试数据
        for i in range(10):
            reinforcer.record_action_feedback(
                action_id=f"action_{i}",
                action_type="reading_list",
                feedback_type="execute",
                success=(i < 8),  # 80% 成功率
            )
        
        metrics = reinforcer.calculate_learning_metrics(days=7)
        
        assert metrics["total_feedback"] == 10
        assert metrics["execute_count"] == 10
        assert metrics["success_count"] == 8
        assert metrics["success_rate"] == pytest.approx(80.0, abs=1.0)
        assert "action_type_stats" in metrics
    
    def test_calculate_learning_metrics_no_data(self, reinforcer):
        """测试无数据时的指标计算"""
        metrics = reinforcer.calculate_learning_metrics(days=7)
        
        assert metrics["total_feedback"] == 0
        assert metrics["execute_rate"] == 0
        assert metrics["success_rate"] == 0
    
    def test_get_action_type_weight_default(self, reinforcer):
        """测试获取默认权重"""
        weight = reinforcer.get_action_type_weight("unknown_type")
        assert weight == 1.0
    
    def test_action_type_stats(self, reinforcer):
        """测试行动类型统计"""
        # 创建不同类型的数据
        reinforcer.record_action_feedback(
            action_id="action_1",
            action_type="reading_list",
            feedback_type="execute",
            success=True,
        )
        reinforcer.record_action_feedback(
            action_id="action_2",
            action_type="github_issue",
            feedback_type="execute",
            success=True,
        )
        reinforcer.record_action_feedback(
            action_id="action_3",
            action_type="reading_list",
            feedback_type="execute",
            success=False,
        )
        
        metrics = reinforcer.calculate_learning_metrics(days=7)
        
        assert "reading_list" in metrics["action_type_stats"]
        assert "github_issue" in metrics["action_type_stats"]
        
        reading_stats = metrics["action_type_stats"]["reading_list"]
        assert reading_stats["count"] == 2
        assert reading_stats["success"] == 1
        assert reading_stats["success_rate"] == pytest.approx(50.0, abs=1.0)

    def test_calculate_learning_metrics_invalid_metadata(self, reinforcer):
        """测试旧数据格式（字符串 metadata）仍能被解析"""
        reinforcer.db.save_reading_behavior(
            {
                "report_id": "legacy_report",
                "item_id": "legacy_action",
                "action": "action_feedback_execute",
                "feedback_type": "execute",
                "section": "action_items",
                "metadata": "legacy_string_metadata",
            }
        )

        metrics = reinforcer.calculate_learning_metrics(days=7)

        assert metrics["total_feedback"] == 1
        assert metrics["execute_count"] == 1
        assert metrics["success_count"] == 0
        assert metrics["action_type_stats"] == {}


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

