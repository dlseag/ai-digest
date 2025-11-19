"""
行动建议生成 Agent
基于内容生成行动建议，并执行工具调用
"""

import logging
from typing import Any, Dict, List, Optional
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_openai import ChatOpenAI

from src.agents.tool_executor import ToolExecutor, parse_tool_calls_from_llm_response
from src.agents.tools import get_tool_schemas

logger = logging.getLogger(__name__)


class ActionAgent:
    """
    行动建议生成 Agent
    
    职责：
    1. 分析内容，生成行动建议
    2. 决定是否需要调用工具
    3. 执行工具调用
    4. 生成最终的行动建议文本
    """
    
    def __init__(
        self,
        llm: Optional[Any] = None,
        tool_executor: Optional[ToolExecutor] = None,
        model_name: str = "gpt-4o-mini",
    ):
        """
        初始化行动 Agent
        
        Args:
            llm: LangChain LLM 实例（可选）
            tool_executor: 工具执行器（可选）
            model_name: LLM 模型名称
        """
        self.llm = llm or ChatOpenAI(
            model=model_name,
            temperature=0,
        )
        self.tool_executor = tool_executor or ToolExecutor()
        self.tool_schemas = get_tool_schemas()
    
    def generate_action_suggestions(
        self,
        items: List[Any],
        max_suggestions: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        为内容生成行动建议
        
        Args:
            items: 内容项目列表
            max_suggestions: 最大建议数量
        
        Returns:
            行动建议列表，每个建议包含：
                - type: 建议类型（"github_issue", "calendar", "reading_list"）
                - title: 建议标题
                - description: 建议描述
                - tool_call: 工具调用信息（如果适用）
                - executed: 是否已执行
                - result: 执行结果（如果已执行）
        """
        if not items:
            return []
        
        # 构建提示
        prompt = self._build_action_prompt(items, max_suggestions)
        
        # 调用 LLM（带工具调用）
        messages = [
            SystemMessage(content=self._get_system_prompt()),
            HumanMessage(content=prompt),
        ]
        
        # 绑定工具
        llm_with_tools = self.llm.bind_tools(self.tool_schemas)
        
        try:
            response = llm_with_tools.invoke(messages)
            
            # 解析工具调用
            tool_calls = parse_tool_calls_from_llm_response(response)
            
            suggestions = []
            
            # 如果有工具调用，执行它们
            if tool_calls:
                logger.info(f"🔧 检测到 {len(tool_calls)} 个工具调用")
                
                for call in tool_calls:
                    tool_name = call.get("name")
                    arguments = call.get("arguments", {})
                    
                    # 执行工具
                    result = self.tool_executor.execute(tool_name, arguments)
                    
                    # 生成建议
                    suggestion = self._create_suggestion_from_tool_call(
                        tool_name,
                        arguments,
                        result,
                    )
                    suggestions.append(suggestion)
            
            # 如果没有工具调用，从 LLM 响应中提取建议
            if not suggestions and hasattr(response, "content"):
                suggestions = self._extract_suggestions_from_text(response.content)
            
            return suggestions[:max_suggestions]
        
        except Exception as e:
            logger.error(f"生成行动建议失败: {e}", exc_info=True)
            return []
    
    def _get_system_prompt(self) -> str:
        """获取系统提示"""
        return """你是一个智能行动建议生成助手。你的职责是：

1. 分析用户提供的内容（文章、论文、项目更新等）
2. 识别可以采取的行动（创建 Issue、安排会议、添加到阅读列表等）
3. 决定是否需要调用工具自动执行行动
4. 生成清晰的行动建议

可用工具：
- create_github_issue: 创建 GitHub Issue（用于记录任务、bug、功能请求）
- send_calendar_invite: 发送日历邀请（用于安排会议或提醒）
- add_to_reading_list: 添加到阅读列表（用于保存需要稍后阅读的内容）

原则：
- 优先自动执行可以立即执行的操作（如添加到阅读列表）
- 对于需要确认的操作（如创建 Issue），先询问用户
- 行动建议应该具体、可操作
- 每个建议应该包含清晰的标题和描述
"""
    
    def _build_action_prompt(self, items: List[Any], max_suggestions: int) -> str:
        """构建行动建议提示"""
        items_text = []
        
        for i, item in enumerate(items[:10], 1):  # 最多分析 10 条
            title = getattr(item, 'title', '')
            summary = getattr(item, 'ai_summary', '') or getattr(item, 'summary', '')
            url = getattr(item, 'url', getattr(item, 'link', ''))
            related_projects = getattr(item, 'related_projects', [])
            
            item_text = f"""
{i}. {title}
   摘要: {summary[:200]}
   URL: {url}
   相关项目: {', '.join(related_projects) if related_projects else '无'}
"""
            items_text.append(item_text)
        
        prompt = f"""请分析以下内容，生成最多 {max_suggestions} 个行动建议。

内容列表：
{''.join(items_text)}

要求：
1. 识别可以采取的具体行动
2. 如果适合，使用工具自动执行（如添加到阅读列表）
3. 对于需要确认的操作，生成建议但不执行
4. 每个建议应该包含：
   - 行动类型
   - 行动标题
   - 行动描述
   - 为什么这个行动有价值

请开始分析并生成行动建议。"""
        
        return prompt
    
    def _create_suggestion_from_tool_call(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Any,
    ) -> Dict[str, Any]:
        """从工具调用创建建议"""
        suggestion_type_map = {
            "create_github_issue": "github_issue",
            "send_calendar_invite": "calendar",
            "add_to_reading_list": "reading_list",
        }
        
        suggestion_type = suggestion_type_map.get(tool_name, "other")
        
        # Phase 2.2: 生成更智能的建议标题（"我已为你..."）
        if tool_name == "create_github_issue":
            if result.success:
                title = f"✓ 我已为你创建了 GitHub Issue: {arguments.get('title', '')}"
            else:
                title = f"创建 GitHub Issue: {arguments.get('title', '')}"
        elif tool_name == "send_calendar_invite":
            if result.success:
                title = f"✓ 我已为你安排了会议: {arguments.get('title', '')}"
            else:
                title = f"安排会议: {arguments.get('title', '')}"
        elif tool_name == "add_to_reading_list":
            if result.success:
                item_title = arguments.get('title', arguments.get('url', ''))
                title = f"✓ 我已为你添加到阅读列表: {item_title}"
            else:
                title = f"添加到阅读列表: {arguments.get('title', arguments.get('url', ''))}"
        else:
            title = f"执行操作: {tool_name}"
        
        # 生成描述（如果已执行，显示执行结果）
        if result.success:
            description = f"✅ {result.message}"
        else:
            description = f"💡 {result.message}\n\n点击 [执行] 按钮完成此操作。"
        
        return {
            "type": suggestion_type,
            "title": title,
            "description": description,
            "tool_call": {
                "name": tool_name,
                "arguments": arguments,
            },
            "executed": result.success,
            "result": result.to_dict() if hasattr(result, 'to_dict') else str(result),
        }
    
    def _extract_suggestions_from_text(self, text: str) -> List[Dict[str, Any]]:
        """从文本中提取建议（备用方法）"""
        # 简单的文本解析（可以改进）
        suggestions = []
        
        # 尝试识别建议格式
        lines = text.split('\n')
        current_suggestion = None
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            # 检测建议标题（以数字或符号开头）
            if line.startswith(('1.', '2.', '3.', '-', '•', '**')):
                if current_suggestion:
                    suggestions.append(current_suggestion)
                
                current_suggestion = {
                    "type": "other",
                    "title": line.lstrip('1234567890.-•* '),
                    "description": "",
                    "executed": False,
                }
            elif current_suggestion:
                current_suggestion["description"] += line + " "
        
        if current_suggestion:
            suggestions.append(current_suggestion)
        
        return suggestions


__all__ = ["ActionAgent"]

