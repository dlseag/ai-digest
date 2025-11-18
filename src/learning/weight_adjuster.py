"""
个性化权重自动调整器
基于用户阅读行为动态调整内容权重
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional
import json

from src.storage.feedback_db import FeedbackDB

logger = logging.getLogger(__name__)


class WeightAdjuster:
    """
    权重自动调整器
    
    基于用户反馈自动调整内容类型权重：
    - 用户多次点赞某类内容 → 提高权重
    - 用户多次踩某类内容 → 降低权重
    - 使用 EMA（指数移动平均）平滑权重变化
    """
    
    def __init__(
        self,
        db: Optional[FeedbackDB] = None,
        config_path: Optional[Path] = None,
        alpha: float = 0.2  # EMA 平滑系数
    ):
        self.db = db or FeedbackDB()
        
        # 配置文件路径
        if config_path is None:
            project_root = Path(__file__).resolve().parents[2]
            config_path = project_root / "config" / "dynamic_weights.json"
        
        self.config_path = config_path
        self.alpha = alpha  # EMA 平滑系数（0-1，越大越敏感）
        
        # 加载当前权重
        self.weights = self._load_weights()
    
    def _load_weights(self) -> Dict[str, Any]:
        """加载当前权重配置"""
        if self.config_path.exists():
            with open(self.config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        
        # 默认权重
        return {
            "content_types": {
                "paper": 1.0,
                "article": 1.0,
                "project": 1.0,
                "framework": 0.8,
                "model": 0.8
            },
            "sources": {},
            "sections": {
                "must_read": 1.0,
                "headlines": 0.8
            },
            "last_updated": datetime.utcnow().isoformat(),
            "adjustments_history": []
        }
    
    def _save_weights(self):
        """保存权重配置"""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.weights["last_updated"] = datetime.utcnow().isoformat()
        
        with open(self.config_path, 'w', encoding='utf-8') as f:
            json.dump(self.weights, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✓ 权重配置已保存: {self.config_path}")
    
    def compute_adjustments(self, days: int = 7) -> Dict[str, Any]:
        """
        计算权重调整
        
        Args:
            days: 分析最近N天的数据
        
        Returns:
            调整建议字典
        """
        logger.info(f"📊 分析最近 {days} 天的阅读行为...")
        
        # 获取行为数据
        behaviors = self.db.get_behaviors(days=days)
        
        if not behaviors:
            logger.warning("⚠️  暂无行为数据，无法调整权重")
            return {"adjustments": [], "message": "暂无数据"}
        
        logger.info(f"✓ 找到 {len(behaviors)} 条行为记录")
        
        # 统计各维度的反馈
        section_feedback = defaultdict(lambda: {"like": 0, "dislike": 0, "neutral": 0})
        source_feedback = defaultdict(lambda: {"like": 0, "dislike": 0, "neutral": 0})
        
        # 从元数据中提取更多信息
        for behavior in behaviors:
            if behavior['action'] != 'feedback':
                continue
            
            feedback_type = behavior.get('feedback_type', 'neutral')
            section = behavior.get('section', 'unknown')
            
            if section != 'unknown':
                section_feedback[section][feedback_type] += 1
            
            # 尝试从元数据中提取来源信息
            metadata = behavior.get('metadata')
            if metadata:
                try:
                    # 处理元数据：可能是字符串、字典或None
                    if isinstance(metadata, str):
                        meta_dict = json.loads(metadata)
                    elif isinstance(metadata, dict):
                        meta_dict = metadata
                    else:
                        continue
                    
                    source = meta_dict.get('source') if isinstance(meta_dict, dict) else None
                    if source:
                        source_feedback[source][feedback_type] += 1
                except (json.JSONDecodeError, TypeError, AttributeError):
                    pass
        
        # 计算权重调整
        adjustments = []
        
        # 1. 调整内容区域权重
        for section, feedback in section_feedback.items():
            total = sum(feedback.values())
            if total < 3:  # 至少3次反馈才调整
                continue
            
            like_rate = feedback['like'] / total
            dislike_rate = feedback['dislike'] / total
            
            current_weight = self.weights["sections"].get(section, 1.0)
            
            # 计算新权重（EMA）
            if like_rate > 0.6:  # 60%+ 点赞
                target_weight = min(current_weight * 1.2, 2.0)
            elif dislike_rate > 0.4:  # 40%+ 踩
                target_weight = max(current_weight * 0.8, 0.3)
            else:
                continue  # 不调整
            
            # EMA 平滑
            new_weight = self.alpha * target_weight + (1 - self.alpha) * current_weight
            
            if abs(new_weight - current_weight) > 0.05:  # 变化超过 5% 才记录
                adjustments.append({
                    "type": "section",
                    "target": section,
                    "old_weight": round(current_weight, 2),
                    "new_weight": round(new_weight, 2),
                    "reason": f"like_rate={like_rate:.1%}, dislike_rate={dislike_rate:.1%}",
                    "feedback_count": total
                })
                
                self.weights["sections"][section] = round(new_weight, 2)
        
        # 2. 调整来源权重
        for source, feedback in source_feedback.items():
            total = sum(feedback.values())
            if total < 5:  # 至少5次反馈才调整来源权重
                continue
            
            like_rate = feedback['like'] / total
            dislike_rate = feedback['dislike'] / total
            
            current_weight = self.weights["sources"].get(source, 1.0)
            
            # 计算新权重
            if like_rate > 0.7:  # 70%+ 点赞
                target_weight = min(current_weight * 1.3, 2.0)
            elif dislike_rate > 0.5:  # 50%+ 踩
                target_weight = max(current_weight * 0.7, 0.2)
            else:
                continue
            
            # EMA 平滑
            new_weight = self.alpha * target_weight + (1 - self.alpha) * current_weight
            
            if abs(new_weight - current_weight) > 0.05:
                adjustments.append({
                    "type": "source",
                    "target": source,
                    "old_weight": round(current_weight, 2),
                    "new_weight": round(new_weight, 2),
                    "reason": f"like_rate={like_rate:.1%}, dislike_rate={dislike_rate:.1%}",
                    "feedback_count": total
                })
                
                self.weights["sources"][source] = round(new_weight, 2)
        
        # 保存调整记录
        if adjustments:
            self.weights["adjustments_history"].append({
                "timestamp": datetime.utcnow().isoformat(),
                "adjustments": adjustments,
                "data_window_days": days
            })
            
            # 只保留最近 20 次调整记录
            self.weights["adjustments_history"] = self.weights["adjustments_history"][-20:]
            
            self._save_weights()
            logger.info(f"✓ 应用了 {len(adjustments)} 项权重调整")
        else:
            logger.info("  无需调整权重（反馈不足或变化不明显）")
        
        return {
            "adjustments": adjustments,
            "total_behaviors": len(behaviors),
            "sections_analyzed": len(section_feedback),
            "sources_analyzed": len(source_feedback)
        }
    
    def get_weight(self, dimension: str, key: str) -> float:
        """
        获取权重
        
        Args:
            dimension: "content_types", "sources", "sections"
            key: 具体的键
        
        Returns:
            权重值（默认 1.0）
        """
        return self.weights.get(dimension, {}).get(key, 1.0)
    
    def get_all_weights(self) -> Dict[str, Any]:
        """获取所有权重"""
        return self.weights.copy()
    
    def reset_weights(self):
        """重置所有权重到默认值"""
        logger.warning("⚠️  重置所有权重到默认值")
        self.weights = self._load_weights()
        self.weights["adjustments_history"].append({
            "timestamp": datetime.utcnow().isoformat(),
            "action": "reset",
            "reason": "manual_reset"
        })
        self._save_weights()


def run_adjustment(days: int = 7, auto_apply: bool = True):
    """运行权重调整（命令行接口）"""
    adjuster = WeightAdjuster()
    
    print("\n" + "=" * 80)
    print("📊 个性化权重自动调整")
    print("=" * 80 + "\n")
    
    result = adjuster.compute_adjustments(days=days)
    
    adjustments = result.get("adjustments", [])
    
    if not adjustments:
        print("✓ 无需调整，当前权重配置良好")
        print(f"\n分析了 {result.get('total_behaviors', 0)} 条行为记录")
        return
    
    print(f"✓ 检测到 {len(adjustments)} 项权重调整:\n")
    
    for i, adj in enumerate(adjustments, 1):
        print(f"{i}. {adj['type'].upper()}: {adj['target']}")
        print(f"   权重: {adj['old_weight']} → {adj['new_weight']}")
        print(f"   原因: {adj['reason']}")
        print(f"   反馈数: {adj['feedback_count']} 次")
        print()
    
    if auto_apply:
        print("✓ 权重已自动应用并保存")
    else:
        print("ℹ️  权重未应用（需要 --auto-apply 标志）")
    
    print("\n" + "=" * 80)
    print("💡 下一步:")
    print("  • 查看权重配置: cat config/dynamic_weights.json")
    print("  • 生成新报告验证效果: python src/main.py --days-back 1")
    print("=" * 80 + "\n")


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='个性化权重自动调整')
    parser.add_argument('--days', type=int, default=7, help='分析最近N天的数据 (默认: 7)')
    parser.add_argument('--auto-apply', action='store_true', help='自动应用调整')
    args = parser.parse_args()
    
    run_adjustment(days=args.days, auto_apply=args.auto_apply)

