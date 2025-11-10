#!/usr/bin/env python3
"""
显式反馈记录脚本
用于记录用户对AI输出的纠正，构建Few-Shot学习数据库
"""

import sys
from pathlib import Path

# 添加项目根目录到Python路径
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from src.learning.explicit_feedback import ExplicitFeedbackManager
from src.storage.feedback_db import FeedbackDB

def record_duplicate_news_correction():
    """记录"必看内容和建议行动重复新闻"的纠正"""
    
    db = FeedbackDB()
    feedback_manager = ExplicitFeedbackManager(db)
    
    # 记录纠正
    feedback_manager.record_correction(
        original_output="""
        必看内容：
        - 6 proven lessons from the AI projects that broke before they scaled (⭐️ 9/10)
        
        建议行动：
        - [6 proven lessons from the AI projects that broke before they scaled](...)：建议详细阅读...
        """,
        corrected_output="""
        必看内容：
        - 6 proven lessons from the AI projects that broke before they scaled (⭐️ 9/10)
        
        建议行动：
        - [Terminal-Bench 2.0 launches...](...)：建议评估...
        （已自动过滤掉重复的"6 proven lessons"）
        """,
        article_context="周报生成 - 必看内容与建议行动去重",
        correction_type="report_deduplication"
    )
    
    print("✅ 已记录纠正：必看内容和建议行动不能重复同一条新闻")
    print("📊 此纠正将用于未来的Few-Shot学习")
    print("\n💡 下次生成报告时，AI会自动参考这个纠正规则")

def main():
    """主函数"""
    print("=" * 60)
    print("显式反馈记录工具")
    print("=" * 60)
    print()
    
    # 记录这次的纠正
    record_duplicate_news_correction()
    
    print("=" * 60)
    print("✓ 完成！AI将在下次生成报告时参考这个纠正。")
    print("=" * 60)

if __name__ == "__main__":
    main()

