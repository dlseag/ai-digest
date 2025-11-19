"""
工具执行器
在 LangGraph 中执行工具调用
"""

import logging
import json
from typing import Any, Dict, List, Optional
from pathlib import Path

from src.agents.tools import (
    ToolResult,
    GitHubIssueTool,
    CalendarInviteTool,
    ReadingListTool,
    TOOLS_REGISTRY,
)

logger = logging.getLogger(__name__)


class ToolExecutor:
    """工具执行器"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化工具执行器
        
        Args:
            config: 工具配置字典
        """
        self.config = config or {}
        
        # 初始化工具实例
        self.tools = {
            "create_github_issue": GitHubIssueTool(
                config=self.config.get("github", {})
            ),
            "send_calendar_invite": CalendarInviteTool(
                config=self.config.get("calendar", {})
            ),
            "add_to_reading_list": ReadingListTool(
                config=self.config.get("reading_list", {})
            ),
        }
    
    def execute(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
    ) -> ToolResult:
        """
        执行工具调用
        
        Args:
            tool_name: 工具名称
            arguments: 工具参数
        
        Returns:
            ToolResult 对象
        """
        if tool_name not in self.tools:
            return ToolResult(
                success=False,
                message=f"未知工具: {tool_name}",
                error="unknown_tool",
            )
        
        tool = self.tools[tool_name]
        
        try:
            logger.info(f"🔧 执行工具: {tool_name} (参数: {arguments})")
            
            # 根据工具名称调用对应方法
            if tool_name == "create_github_issue":
                result = tool.create_issue(**arguments)
            elif tool_name == "send_calendar_invite":
                result = tool.send_invite(**arguments)
            elif tool_name == "add_to_reading_list":
                result = tool.add_to_list(**arguments)
            else:
                return ToolResult(
                    success=False,
                    message=f"工具 {tool_name} 未实现执行逻辑",
                    error="not_implemented",
                )
            
            if result.success:
                logger.info(f"✓ 工具执行成功: {tool_name}")
            else:
                logger.warning(f"⚠️  工具执行失败: {tool_name} - {result.message}")
            
            return result
        except Exception as e:
            logger.error(f"工具执行异常: {tool_name} - {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"执行异常: {str(e)}",
                error=str(e),
            )
    
    def execute_batch(
        self,
        tool_calls: List[Dict[str, Any]],
    ) -> List[ToolResult]:
        """
        批量执行工具调用
        
        Args:
            tool_calls: 工具调用列表，每个元素包含：
                - name: 工具名称
                - arguments: 工具参数
        
        Returns:
            ToolResult 列表
        """
        results = []
        for call in tool_calls:
            name = call.get("name")
            arguments = call.get("arguments", {})
            
            if not name:
                results.append(ToolResult(
                    success=False,
                    message="工具调用缺少名称",
                    error="missing_name",
                ))
                continue
            
            result = self.execute(name, arguments)
            results.append(result)
        
        return results


def parse_tool_calls_from_llm_response(
    response: Any,
) -> List[Dict[str, Any]]:
    """
    从 LLM 响应中解析工具调用
    
    支持多种格式：
    1. OpenAI Function Calling 格式
    2. LangChain Tool Calling 格式
    3. 自定义格式
    
    Args:
        response: LLM 响应对象
    
    Returns:
        工具调用列表
    """
    tool_calls = []
    
    # 检查是否是 OpenAI 格式
    if hasattr(response, "tool_calls") and response.tool_calls:
        for call in response.tool_calls:
            tool_calls.append({
                "name": call.get("function", {}).get("name"),
                "arguments": json.loads(call.get("function", {}).get("arguments", "{}")),
            })
        return tool_calls
    
    # 检查是否是 LangChain 格式
    if hasattr(response, "tool_calls") and isinstance(response.tool_calls, list):
        for call in response.tool_calls:
            tool_calls.append({
                "name": call.get("name") or call.get("tool"),
                "arguments": call.get("args", {}),
            })
        return tool_calls
    
    # 检查响应内容中是否包含工具调用（自定义格式）
    if hasattr(response, "content"):
        content = response.content
        # 尝试解析 JSON 格式的工具调用
        try:
            if isinstance(content, str) and content.strip().startswith("{"):
                parsed = json.loads(content)
                if "tool_calls" in parsed:
                    return parsed["tool_calls"]
        except json.JSONDecodeError:
            pass
    
    return tool_calls


__all__ = ["ToolExecutor", "parse_tool_calls_from_llm_response"]

