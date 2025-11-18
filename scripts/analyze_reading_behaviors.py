#!/usr/bin/env python3
"""
阅读行为分析工具
分析用户的阅读习惯和偏好
"""

import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.storage.feedback_db import FeedbackDB


def analyze_behaviors(days: int = 7):
    """分析最近N天的阅读行为"""
    db = FeedbackDB()
    
    print("\n" + "=" * 80)
    print(f"📊 AI简报阅读行为分析 (最近 {days} 天)")
    print("=" * 80 + "\n")
    
    # 获取所有行为数据
    behaviors = db.get_behaviors(days=days)
    
    if not behaviors:
        print("⚠️  暂无阅读行为数据")
        print("\n提示:")
        print("  1. 启动追踪服务器: ./scripts/start_tracking_server.sh")
        print("  2. 打开 HTML 报告并与内容互动")
        print("  3. 再次运行此脚本查看分析结果\n")
        return
    
    print(f"✓ 找到 {len(behaviors)} 条行为记录\n")
    
    # 按行为类型统计
    action_counts = defaultdict(int)
    feedback_types = defaultdict(int)
    section_counts = defaultdict(int)
    
    # 详细统计
    total_read_time = 0
    click_count = 0
    view_count = 0
    feedback_count = 0
    
    for behavior in behaviors:
        action = behavior['action']
        action_counts[action] += 1
        
        if action == 'feedback':
            feedback_type = behavior.get('feedback_type', 'unknown')
            feedback_types[feedback_type] += 1
            feedback_count += 1
        elif action == 'click':
            click_count += 1
        elif action == 'view':
            view_count += 1
        elif action == 'read_time':
            read_time = behavior.get('read_time', 0)
            if read_time:
                total_read_time += read_time
        
        section = behavior.get('section', 'unknown')
        if section != 'unknown':
            section_counts[section] += 1
    
    # 1. 行为类型分布
    print("📈 行为类型分布")
    print("-" * 80)
    for action, count in sorted(action_counts.items(), key=lambda x: x[1], reverse=True):
        percentage = (count / len(behaviors)) * 100
        bar = "█" * int(percentage / 2)
        print(f"  {action:15s} {count:4d} 次 ({percentage:5.1f}%) {bar}")
    print()
    
    # 2. 反馈情况
    if feedback_types:
        print("👍 用户反馈统计")
        print("-" * 80)
        for feedback, count in sorted(feedback_types.items(), key=lambda x: x[1], reverse=True):
            emoji = {"like": "👍", "dislike": "👎", "neutral": "➖"}.get(feedback, "❓")
            percentage = (count / feedback_count) * 100
            print(f"  {emoji} {feedback:10s} {count:4d} 次 ({percentage:5.1f}%)")
        print()
    
    # 3. 内容区域热度
    if section_counts:
        print("🔥 内容区域热度")
        print("-" * 80)
        for section, count in sorted(section_counts.items(), key=lambda x: x[1], reverse=True):
            emoji = {"must_read": "⭐", "headlines": "🔥", "insights": "💡"}.get(section, "📄")
            print(f"  {emoji} {section:15s} {count:4d} 次互动")
        print()
    
    # 4. 关键指标
    print("📊 关键指标")
    print("-" * 80)
    
    # 阅读率 = (浏览数 + 点击数) / 总项目数
    engagement_count = view_count + click_count
    engagement_rate = (engagement_count / len(behaviors)) * 100 if behaviors else 0
    
    # 点击率 = 点击数 / 浏览数
    click_through_rate = (click_count / view_count * 100) if view_count > 0 else 0
    
    # 反馈率 = 反馈数 / (浏览数 + 点击数)
    feedback_rate = (feedback_count / engagement_count * 100) if engagement_count > 0 else 0
    
    # 平均阅读时长
    avg_read_time = total_read_time / 1000 / 60  # 转换为分钟
    
    print(f"  💚 参与率 (Engagement):     {engagement_rate:>6.1f}%")
    print(f"  🖱️  点击率 (CTR):            {click_through_rate:>6.1f}%")
    print(f"  💬 反馈率:                   {feedback_rate:>6.1f}%")
    print(f"  ⏱️  总阅读时长:              {avg_read_time:>6.1f} 分钟")
    print()
    
    # 5. 内容偏好洞察
    print("💡 内容偏好洞察")
    print("-" * 80)
    
    liked_count = feedback_types.get('like', 0)
    disliked_count = feedback_types.get('dislike', 0)
    neutral_count = feedback_types.get('neutral', 0)
    
    if liked_count > disliked_count * 2:
        print("  ✓ 内容质量良好，用户满意度高")
    elif disliked_count > liked_count:
        print("  ⚠️  内容质量需要改进，用户不满意内容较多")
    
    if click_through_rate < 30:
        print("  ⚠️  点击率偏低，建议优化摘要质量或调整内容推荐")
    elif click_through_rate > 60:
        print("  ✓ 点击率很高，内容吸引力强")
    
    if feedback_rate < 20:
        print("  ℹ️  用户反馈较少，可以引导用户提供更多反馈")
    elif feedback_rate > 50:
        print("  ✓ 用户反馈积极，参与度高")
    
    # 6. 最活跃的报告
    report_activity = defaultdict(int)
    for behavior in behaviors:
        report_id = behavior.get('report_id', 'unknown')
        if report_id != 'unknown':
            report_activity[report_id] += 1
    
    if report_activity:
        print("\n📅 最活跃的报告")
        print("-" * 80)
        for report_id, count in sorted(report_activity.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"  {report_id:30s} {count:4d} 次互动")
    
    print("\n" + "=" * 80)
    print("💡 下一步建议:")
    print("  • 基于这些数据调整内容权重 (Phase 1.2)")
    print("  • 优化相关性排序算法 (Phase 1.3)")
    print("  • 实现个性化推荐 (Phase 2)")
    print("=" * 80 + "\n")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='分析 AI 简报阅读行为')
    parser.add_argument('--days', type=int, default=7, help='分析最近N天的数据 (默认: 7)')
    args = parser.parse_args()
    
    analyze_behaviors(days=args.days)

