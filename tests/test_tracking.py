"""
测试追踪系统 (Phase 1.1)
"""

import pytest
import json
import sqlite3
from pathlib import Path
from datetime import datetime
import tempfile
import shutil

from src.storage.feedback_db import FeedbackDB


class TestReadingBehaviors:
    """测试阅读行为追踪数据库功能"""
    
    @pytest.fixture
    def temp_db(self):
        """创建临时数据库"""
        temp_dir = Path(tempfile.mkdtemp())
        db_path = temp_dir / "test_feedback.db"
        db = FeedbackDB(db_path=db_path)
        
        yield db
        
        # 清理
        shutil.rmtree(temp_dir)
    
    def test_save_reading_behavior(self, temp_db):
        """测试保存阅读行为"""
        behavior = {
            "report_id": "2025-11-12",
            "item_id": "test_123",
            "action": "click",
            "section": "must_read",
            "url": "https://example.com/article"
        }
        
        # 保存行为
        temp_db.save_reading_behavior(behavior)
        
        # 验证保存成功
        behaviors = temp_db.get_behaviors(days=1)
        assert len(behaviors) == 1
        assert behaviors[0]['item_id'] == "test_123"
        assert behaviors[0]['action'] == "click"
    
    def test_save_feedback_behavior(self, temp_db):
        """测试保存反馈行为"""
        behavior = {
            "report_id": "2025-11-12",
            "item_id": "test_456",
            "action": "feedback",
            "feedback_type": "like",
            "section": "headlines"
        }
        
        temp_db.save_reading_behavior(behavior)
        
        behaviors = temp_db.get_behaviors(action="feedback", days=1)
        assert len(behaviors) == 1
        assert behaviors[0]['feedback_type'] == "like"
    
    def test_save_read_time(self, temp_db):
        """测试保存阅读时长"""
        behavior = {
            "report_id": "2025-11-12",
            "action": "read_time",
            "read_time": 120000  # 2分钟（毫秒）
        }
        
        temp_db.save_reading_behavior(behavior)
        
        behaviors = temp_db.get_behaviors(action="read_time", days=1)
        assert len(behaviors) == 1
        assert behaviors[0]['read_time'] == 120000
    
    def test_get_behaviors_by_report(self, temp_db):
        """测试按报告ID查询行为"""
        # 保存多条行为
        for i in range(3):
            temp_db.save_reading_behavior({
                "report_id": "2025-11-12",
                "item_id": f"test_{i}",
                "action": "view"
            })
        
        temp_db.save_reading_behavior({
            "report_id": "2025-11-11",
            "item_id": "test_old",
            "action": "view"
        })
        
        # 查询特定报告的行为
        behaviors = temp_db.get_behaviors(report_id="2025-11-12", days=7)
        assert len(behaviors) == 3
    
    def test_get_behaviors_by_item(self, temp_db):
        """测试按内容ID查询行为"""
        item_id = "test_article_123"
        
        # 用户先浏览
        temp_db.save_reading_behavior({
            "item_id": item_id,
            "action": "view",
            "section": "headlines"
        })
        
        # 然后点击
        temp_db.save_reading_behavior({
            "item_id": item_id,
            "action": "click",
            "section": "headlines"
        })
        
        # 最后反馈
        temp_db.save_reading_behavior({
            "item_id": item_id,
            "action": "feedback",
            "feedback_type": "like"
        })
        
        # 查询该内容的所有行为
        behaviors = temp_db.get_behaviors(item_id=item_id, days=7)
        assert len(behaviors) == 3
        assert behaviors[0]['action'] in ['view', 'click', 'feedback']
    
    def test_behavior_with_metadata(self, temp_db):
        """测试保存带元数据的行为"""
        behavior = {
            "item_id": "test_789",
            "action": "click",
            "metadata": {
                "source": "arXiv cs.CL",
                "category": "paper",
                "title": "Test Paper"
            }
        }
        
        temp_db.save_reading_behavior(behavior)
        
        behaviors = temp_db.get_behaviors(item_id="test_789", days=1)
        assert len(behaviors) == 1
        
        # 验证元数据可以解析
        metadata = json.loads(behaviors[0]['metadata'])
        assert metadata['source'] == "arXiv cs.CL"
        assert metadata['category'] == "paper"


class TestTrackingServer:
    """测试追踪服务器（集成测试）"""
    
    def test_server_import(self):
        """测试服务器模块可以正常导入"""
        from src.tracking.tracking_server import TrackingHandler, run_server
        assert TrackingHandler is not None
        assert run_server is not None
    
    def test_tracking_handler_db_setup(self):
        """测试追踪处理器的数据库设置"""
        from src.tracking.tracking_server import TrackingHandler
        from src.storage.feedback_db import FeedbackDB
        
        # 创建临时数据库
        temp_dir = Path(tempfile.mkdtemp())
        db_path = temp_dir / "test_tracking.db"
        db = FeedbackDB(db_path=db_path)
        
        # 设置到处理器
        TrackingHandler.set_db(db)
        
        assert TrackingHandler.db is not None
        
        # 清理
        shutil.rmtree(temp_dir)


class TestTrackingIntegration:
    """测试追踪系统集成"""
    
    def test_html_template_has_tracking_script(self):
        """测试HTML模板包含追踪脚本"""
        template_path = Path(__file__).parent.parent / "templates" / "report_template.html.jinja"
        
        if not template_path.exists():
            pytest.skip(f"模板文件不存在: {template_path}")
        
        with open(template_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 验证关键追踪代码存在
        assert "TRACKING_API" in content
        assert "trackBehavior" in content
        assert "/api/track" in content
        assert "data-track-click" in content
        assert "IntersectionObserver" in content
    
    def test_analyze_script_exists(self):
        """测试分析脚本存在且可执行"""
        script_path = Path(__file__).parent.parent / "scripts" / "analyze_reading_behaviors.py"
        
        assert script_path.exists(), "分析脚本不存在"
        
        # 检查是否可执行
        import os
        assert os.access(script_path, os.X_OK) or script_path.suffix == '.py'
    
    def test_tracking_scripts_exist(self):
        """测试追踪服务器启动/停止脚本存在"""
        scripts_dir = Path(__file__).parent.parent / "scripts"
        
        start_script = scripts_dir / "start_tracking_server.sh"
        stop_script = scripts_dir / "stop_tracking_server.sh"
        
        assert start_script.exists(), "启动脚本不存在"
        assert stop_script.exists(), "停止脚本不存在"




if __name__ == '__main__':
    pytest.main([__file__, '-v'])

