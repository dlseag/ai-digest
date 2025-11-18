"""
反馈闭环优化
基于用户反馈和行动执行结果强化学习
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from src.storage.feedback_db import FeedbackDB
from src.learning.weight_adjuster import WeightAdjuster

logger = logging.getLogger(__name__)


class FeedbackLearningEngine:
    """
    反馈学习引擎
    
    职责：
    1. 分析用户反馈（👍/👎/执行/跳过）
    2. 分析行动执行成功率
    3. 强化权重调整
    4. 优化行动建议生成策略
    """
    
    def __init__(
        self,
        db: Optional[FeedbackDB] = None,
        weight_adjuster: Optional[WeightAdjuster] = None,
    ):
        self.db = db or FeedbackDB()
        self.weight_adjuster = weight_adjuster or WeightAdjuster()
    
    def analyze_feedback_patterns(self, days: int = 7) -> Dict[str, Any]:
        """
        分析反馈模式
        
        Args:
            days: 分析最近N天的数据
        
        Returns:
            反馈模式分析结果
        """
        logger.info(f"📊 分析最近 {days} 天的反馈模式...")
        
        behaviors = self.db.get_behaviors(days=days)
        
        if not behaviors:
            return {
                "total_behaviors": 0,
                "patterns": {},
                "insights": [],
            }
        
        # 统计反馈类型
        feedback_counts = defaultdict(int)
        action_execution_counts = defaultdict(lambda: {"success": 0, "failed": 0, "skipped": 0})
        source_feedback = defaultdict(lambda: {"like": 0, "dislike": 0, "neutral": 0})
        section_feedback = defaultdict(lambda: {"like": 0, "dislike": 0, "neutral": 0})
        
        for behavior in behaviors:
            action = behavior.get('action')
            
            if action == 'feedback':
                feedback_type = behavior.get('feedback_type', 'neutral')
                feedback_counts[feedback_type] += 1
                
                # 按来源统计
                metadata = behavior.get('metadata')
                if metadata:
                    try:
                        import json
                        meta_dict = json.loads(metadata) if isinstance(metadata, str) else metadata
                        source = meta_dict.get('source')
                        if source:
                            source_feedback[source][feedback_type] += 1
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                # 按区域统计
                section = behavior.get('section', 'unknown')
                if section != 'unknown':
                    section_feedback[section][feedback_type] += 1
            
            elif action == 'execute_action':
                tool_name = behavior.get('metadata', {})
                if isinstance(tool_name, str):
                    try:
                        import json
                        meta_dict = json.loads(tool_name)
                        tool_name = meta_dict.get('tool_name', 'unknown')
                    except (json.JSONDecodeError, TypeError):
                        tool_name = 'unknown'
                
                feedback_type = behavior.get('feedback_type', 'failed')
                if feedback_type == 'success':
                    action_execution_counts[tool_name]["success"] += 1
                else:
                    action_execution_counts[tool_name]["failed"] += 1
            
            elif action == 'skip_action':
                tool_name = behavior.get('metadata', {})
                if isinstance(tool_name, str):
                    try:
                        import json
                        meta_dict = json.loads(tool_name)
                        tool_name = meta_dict.get('tool_name', 'unknown')
                    except (json.JSONDecodeError, TypeError):
                        tool_name = 'unknown'
                
                action_execution_counts[tool_name]["skipped"] += 1
        
        # 计算关键指标
        total_feedback = sum(feedback_counts.values())
        like_rate = feedback_counts.get('like', 0) / total_feedback if total_feedback > 0 else 0
        dislike_rate = feedback_counts.get('dislike', 0) / total_feedback if total_feedback > 0 else 0
        
        # 行动执行成功率
        action_success_rate = {}
        for tool_name, counts in action_execution_counts.items():
            total = counts["success"] + counts["failed"]
            if total > 0:
                action_success_rate[tool_name] = {
                    "success_rate": counts["success"] / total,
                    "total_executions": total,
                    "skipped": counts["skipped"],
                }
        
        # 生成洞察
        insights = []
        
        if like_rate > 0.6:
            insights.append("用户满意度高，内容质量良好")
        elif dislike_rate > 0.3:
            insights.append("用户不满意内容较多，需要改进内容推荐")
        
        # 分析最受欢迎的来源
        if source_feedback:
            best_source = max(
                source_feedback.items(),
                key=lambda x: x[1].get('like', 0) / max(sum(x[1].values()), 1)
            )
            if best_source[1].get('like', 0) > 0:
                insights.append(f"最受欢迎来源: {best_source[0]}")
        
        # 分析行动执行成功率
        if action_success_rate:
            best_tool = max(
                action_success_rate.items(),
                key=lambda x: x[1].get("success_rate", 0)
            )
            if best_tool[1]["success_rate"] > 0.7:
                insights.append(f"工具 '{best_tool[0]}' 执行成功率最高 ({best_tool[1]['success_rate']:.1%})")
        
        return {
            "total_behaviors": len(behaviors),
            "total_feedback": total_feedback,
            "feedback_distribution": dict(feedback_counts),
            "like_rate": like_rate,
            "dislike_rate": dislike_rate,
            "action_execution_rates": action_success_rate,
            "source_feedback": dict(source_feedback),
            "section_feedback": dict(section_feedback),
            "insights": insights,
        }
    
    def reinforce_weights(self, days: int = 7) -> Dict[str, Any]:
        """
        基于反馈强化权重
        
        Args:
            days: 分析最近N天的数据
        
        Returns:
            权重调整结果
        """
        logger.info(f"🔄 基于反馈强化权重（最近 {days} 天）...")
        
        # 分析反馈模式
        patterns = self.analyze_feedback_patterns(days=days)
        
        if patterns["total_feedback"] < 5:
            logger.info("  反馈数据不足，跳过权重强化")
            return {
                "adjusted": False,
                "reason": "insufficient_feedback",
            }
        
        adjustments = []
        
        # 1. 基于来源反馈调整来源权重
        source_feedback = patterns.get("source_feedback", {})
        for source, feedback in source_feedback.items():
            total = sum(feedback.values())
            if total < 3:
                continue
            
            like_rate = feedback.get('like', 0) / total
            dislike_rate = feedback.get('dislike', 0) / total
            
            current_weight = self.weight_adjuster.get_weight('sources', source)
            
            # 如果点赞率 > 70%，提升权重
            if like_rate > 0.7:
                target_weight = min(current_weight * 1.2, 2.0)
                new_weight = 0.3 * target_weight + 0.7 * current_weight  # EMA
                
                if abs(new_weight - current_weight) > 0.05:
                    self.weight_adjuster.weights["sources"][source] = round(new_weight, 2)
                    adjustments.append({
                        "type": "source",
                        "target": source,
                        "old_weight": current_weight,
                        "new_weight": new_weight,
                        "reason": f"like_rate={like_rate:.1%}",
                    })
            
            # 如果踩率 > 50%，降低权重
            elif dislike_rate > 0.5:
                target_weight = max(current_weight * 0.8, 0.2)
                new_weight = 0.3 * target_weight + 0.7 * current_weight  # EMA
                
                if abs(new_weight - current_weight) > 0.05:
                    self.weight_adjuster.weights["sources"][source] = round(new_weight, 2)
                    adjustments.append({
                        "type": "source",
                        "target": source,
                        "old_weight": current_weight,
                        "new_weight": new_weight,
                        "reason": f"dislike_rate={dislike_rate:.1%}",
                    })
        
        # 2. 基于区域反馈调整区域权重
        section_feedback = patterns.get("section_feedback", {})
        for section, feedback in section_feedback.items():
            total = sum(feedback.values())
            if total < 3:
                continue
            
            like_rate = feedback.get('like', 0) / total
            dislike_rate = feedback.get('dislike', 0) / total
            
            current_weight = self.weight_adjuster.get_weight('sections', section)
            
            if like_rate > 0.6:
                target_weight = min(current_weight * 1.15, 2.0)
                new_weight = 0.3 * target_weight + 0.7 * current_weight
                
                if abs(new_weight - current_weight) > 0.05:
                    self.weight_adjuster.weights["sections"][section] = round(new_weight, 2)
                    adjustments.append({
                        "type": "section",
                        "target": section,
                        "old_weight": current_weight,
                        "new_weight": new_weight,
                        "reason": f"like_rate={like_rate:.1%}",
                    })
            elif dislike_rate > 0.4:
                target_weight = max(current_weight * 0.85, 0.3)
                new_weight = 0.3 * target_weight + 0.7 * current_weight
                
                if abs(new_weight - current_weight) > 0.05:
                    self.weight_adjuster.weights["sections"][section] = round(new_weight, 2)
                    adjustments.append({
                        "type": "section",
                        "target": section,
                        "old_weight": current_weight,
                        "new_weight": new_weight,
                        "reason": f"dislike_rate={dislike_rate:.1%}",
                    })
        
        # 保存权重
        if adjustments:
            self.weight_adjuster._save_weights()
            logger.info(f"✓ 强化了 {len(adjustments)} 项权重")
        else:
            logger.info("  无需调整权重")
        
        return {
            "adjusted": len(adjustments) > 0,
            "adjustments": adjustments,
            "patterns": patterns,
        }
    
    def get_actionability_metrics(self, days: int = 7) -> Dict[str, Any]:
        """
        计算可操作性指标
        
        Args:
            days: 分析最近N天的数据
        
        Returns:
            可操作性指标
        """
        behaviors = self.db.get_behaviors(days=days)
        
        # 统计行动相关行为
        total_actions_suggested = 0
        total_actions_executed = 0
        total_actions_skipped = 0
        
        for behavior in behaviors:
            action = behavior.get('action')
            if action == 'execute_action':
                total_actions_executed += 1
            elif action == 'skip_action':
                total_actions_skipped += 1
        
        # 估算建议的行动数（通过执行+跳过）
        total_actions_suggested = total_actions_executed + total_actions_skipped
        
        # 计算可操作性率
        actionability_rate = (
            total_actions_executed / total_actions_suggested
            if total_actions_suggested > 0
            else 0.0
        )
        
        # 计算执行成功率
        execution_success = 0
        execution_failed = 0
        
        for behavior in behaviors:
            if behavior.get('action') == 'execute_action':
                if behavior.get('feedback_type') == 'success':
                    execution_success += 1
                else:
                    execution_failed += 1
        
        execution_success_rate = (
            execution_success / (execution_success + execution_failed)
            if (execution_success + execution_failed) > 0
            else 0.0
        )
        
        return {
            "total_actions_suggested": total_actions_suggested,
            "total_actions_executed": total_actions_executed,
            "total_actions_skipped": total_actions_skipped,
            "actionability_rate": actionability_rate,
            "execution_success": execution_success,
            "execution_failed": execution_failed,
            "execution_success_rate": execution_success_rate,
        }


def run_feedback_learning(days: int = 7, auto_reinforce: bool = True):
    """运行反馈学习（命令行接口）"""
    engine = FeedbackLearningEngine()
    
    print("\n" + "=" * 80)
    print("📊 反馈闭环优化分析")
    print("=" * 80 + "\n")
    
    # 1. 分析反馈模式
    patterns = engine.analyze_feedback_patterns(days=days)
    
    print(f"✓ 分析了 {patterns['total_behaviors']} 条行为记录")
    print(f"  反馈总数: {patterns.get('total_feedback', 0)}")
    print(f"  点赞率: {patterns.get('like_rate', 0):.1%}")
    print(f"  踩率: {patterns.get('dislike_rate', 0):.1%}")
    print()
    
    # 2. 显示洞察
    insights = patterns.get('insights', [])
    if insights:
        print("💡 关键洞察:")
        for insight in insights:
            print(f"  • {insight}")
        print()
    
    # 3. 显示行动执行统计
    action_rates = patterns.get('action_execution_rates', {})
    if action_rates:
        print("🔧 行动执行统计:")
        for tool_name, stats in action_rates.items():
            print(f"  • {tool_name}:")
            print(f"    成功率: {stats['success_rate']:.1%}")
            print(f"    执行次数: {stats['total_executions']}")
            print(f"    跳过次数: {stats['skipped']}")
        print()
    
    # 4. 强化权重
    if auto_reinforce:
        result = engine.reinforce_weights(days=days)
        
        if result['adjusted']:
            print("✓ 权重已强化:")
            for adj in result['adjustments']:
                print(f"  • {adj['type']}: {adj['target']}")
                print(f"    {adj['old_weight']} → {adj['new_weight']} ({adj['reason']})")
        else:
            print("ℹ️  无需调整权重")
        print()
    
    # 5. 可操作性指标
    metrics = engine.get_actionability_metrics(days=days)
    print("📈 可操作性指标:")
    print(f"  建议行动数: {metrics['total_actions_suggested']}")
    print(f"  执行行动数: {metrics['total_actions_executed']}")
    print(f"  跳过行动数: {metrics['total_actions_skipped']}")
    print(f"  可操作性率: {metrics['actionability_rate']:.1%}")
    print(f"  执行成功率: {metrics['execution_success_rate']:.1%}")
    print()
    
    print("=" * 80 + "\n")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='反馈闭环优化')
    parser.add_argument('--days', type=int, default=7, help='分析最近N天的数据')
    parser.add_argument('--no-reinforce', action='store_true', help='不自动强化权重')
    args = parser.parse_args()
    
    run_feedback_learning(days=args.days, auto_reinforce=not args.no_reinforce)

