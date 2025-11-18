"""
反馈闭环优化器
基于用户反馈强化行动权重和学习
"""

import json
import logging
from typing import Dict, List, Any, Optional, Union
from collections import defaultdict
from datetime import datetime, timedelta

from src.storage.feedback_db import FeedbackDB
from src.learning.weight_adjuster import WeightAdjuster

logger = logging.getLogger(__name__)


class FeedbackReinforcer:
    """
    反馈强化器
    
    职责：
    1. 记录用户反馈（执行/跳过/不相关）
    2. 基于反馈强化行动类型权重
    3. 计算学习速度指标
    """
    
    def __init__(
        self,
        db: Optional[FeedbackDB] = None,
        weight_adjuster: Optional[WeightAdjuster] = None,
    ):
        """
        初始化反馈强化器
        
        Args:
            db: 反馈数据库
            weight_adjuster: 权重调整器（用于强化权重）
        """
        self.db = db or FeedbackDB()
        self.weight_adjuster = weight_adjuster or WeightAdjuster()
    
    def record_action_feedback(
        self,
        action_id: str,
        action_type: str,
        feedback_type: str,  # "execute", "skip", "irrelevant"
        tool_name: Optional[str] = None,
        success: Optional[bool] = None,
    ) -> None:
        """
        记录行动反馈
        
        Args:
            action_id: 行动 ID
            action_type: 行动类型（"github_issue", "calendar", "reading_list"）
            feedback_type: 反馈类型（"execute", "skip", "irrelevant"）
            tool_name: 工具名称（可选）
            success: 执行是否成功（可选）
        """
        try:
            self.db.save_reading_behavior({
                "report_id": "unknown",
                "item_id": action_id,
                "action": f"action_feedback_{feedback_type}",
                "feedback_type": feedback_type,
                "section": "action_items",
                "metadata": {
                    "action_type": action_type,
                    "tool_name": tool_name,
                    "success": success,
                },
            })
            
            logger.info(f"✓ 记录行动反馈: {action_type} - {feedback_type}")
            
            # 如果执行成功，强化权重
            if feedback_type == "execute" and success:
                self._reinforce_action_weight(action_type, tool_name)
            
        except Exception as e:
            logger.error(f"记录行动反馈失败: {e}", exc_info=True)
    
    def _reinforce_action_weight(self, action_type: str, tool_name: Optional[str] = None):
        """
        强化行动类型权重
        
        Args:
            action_type: 行动类型
            tool_name: 工具名称
        """
        try:
            # 获取当前权重
            weights = self.weight_adjuster.get_all_weights()
            
            # 创建或更新行动类型权重
            if "action_types" not in weights:
                weights["action_types"] = {}
            
            current_weight = weights["action_types"].get(action_type, 1.0)
            
            # 增加权重（EMA 平滑）
            new_weight = min(2.0, current_weight * 1.1)  # 增加 10%，上限 2.0
            
            weights["action_types"][action_type] = new_weight
            
            # 保存权重
            self.weight_adjuster.weights = weights
            self.weight_adjuster._save_weights()
            
            logger.info(f"✓ 强化行动权重: {action_type} {current_weight:.2f} → {new_weight:.2f}")
            
        except Exception as e:
            logger.warning(f"强化权重失败: {e}")
    
    def calculate_learning_metrics(self, days: int = 7) -> Dict[str, Any]:
        """
        计算学习指标
        
        Args:
            days: 分析最近 N 天的数据
        
        Returns:
            学习指标字典
        """
        try:
            # 获取行动反馈数据
            behaviors = self.db.get_behaviors(
                action="action_feedback_execute",
                days=days,
            )
            
            # 统计
            total_feedback = len(behaviors)
            execute_count = 0
            skip_count = 0
            success_count = 0
            
            action_type_counts = defaultdict(int)
            action_type_success = defaultdict(int)
            
            for behavior in behaviors:
                feedback_type = behavior.get("feedback_type", "")
                metadata = self._normalize_metadata(behavior.get("metadata"))

                action_type = metadata.get("action_type", "unknown")
                success = metadata.get("success", False)
                
                if feedback_type == "execute":
                    execute_count += 1
                    if action_type != "unknown":
                        action_type_counts[action_type] += 1
                        if success:
                            action_type_success[action_type] += 1
                    if success:
                        success_count += 1
                elif feedback_type == "skip":
                    skip_count += 1
            
            # 计算指标
            execute_rate = (execute_count / total_feedback * 100) if total_feedback > 0 else 0
            success_rate = (success_count / execute_count * 100) if execute_count > 0 else 0
            
            # 计算学习速度（简化版：成功率提升）
            # 实际应该对比历史数据
            learning_speed = success_rate  # 简化：使用当前成功率
            
            return {
                "total_feedback": total_feedback,
                "execute_count": execute_count,
                "skip_count": skip_count,
                "success_count": success_count,
                "execute_rate": round(execute_rate, 2),
                "success_rate": round(success_rate, 2),
                "learning_speed": round(learning_speed, 2),
                "action_type_stats": {
                    action_type: {
                        "count": action_type_counts[action_type],
                        "success": action_type_success[action_type],
                        "success_rate": round(
                            (action_type_success[action_type] / action_type_counts[action_type] * 100)
                            if action_type_counts[action_type] > 0 else 0,
                            2
                        ),
                    }
                    for action_type in action_type_counts.keys()
                },
            }
        except Exception as e:
            logger.error(f"计算学习指标失败: {e}", exc_info=True)
            return {
                "total_feedback": 0,
                "execute_rate": 0,
                "success_rate": 0,
                "learning_speed": 0,
            }
    
    def get_action_type_weight(self, action_type: str) -> float:
        """
        获取行动类型权重
        
        Args:
            action_type: 行动类型
        
        Returns:
            权重值（默认 1.0）
        """
        weights = self.weight_adjuster.get_all_weights()
        action_types = weights.get("action_types", {})
        return action_types.get(action_type, 1.0)

    @staticmethod
    def _normalize_metadata(metadata: Union[str, bytes, Dict[str, Any], None]) -> Dict[str, Any]:
        """
        兼容性解析 metadata 字段，确保返回字典。
        元数据可能以 JSON 字符串、字节或已解析的字典形式存储。
        """
        if metadata is None:
            return {}

        if isinstance(metadata, dict):
            return metadata

        if isinstance(metadata, (bytes, bytearray)):
            metadata = metadata.decode("utf-8", errors="ignore")

        if isinstance(metadata, str):
            metadata = metadata.strip()
            if not metadata:
                return {}
            try:
                parsed = json.loads(metadata)
            except json.JSONDecodeError:
                logger.debug("无法解析 metadata JSON: %s", metadata)
                return {}
            if isinstance(parsed, dict):
                return parsed
            if isinstance(parsed, str):
                # 兼容 legacy 双重序列化（字符串里再包 JSON）
                try:
                    nested = json.loads(parsed)
                    return nested if isinstance(nested, dict) else {}
                except json.JSONDecodeError:
                    return {}
            return {}

        # 其他未知类型直接忽略
        return {}


__all__ = ["FeedbackReinforcer"]

