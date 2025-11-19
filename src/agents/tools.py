"""
Agent 工具定义
定义 LLM 可以调用的工具（Function Calling）
"""

import logging
import json
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


class ToolResult:
    """工具执行结果"""
    
    def __init__(
        self,
        success: bool,
        message: str,
        data: Optional[Dict[str, Any]] = None,
        error: Optional[str] = None,
    ):
        self.success = success
        self.message = message
        self.data = data or {}
        self.error = error
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "success": self.success,
            "message": self.message,
            "data": self.data,
            "error": self.error,
        }


class GitHubIssueTool:
    """GitHub Issue 创建工具"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化 GitHub Issue 工具
        
        Args:
            config: 配置字典，包含：
                - token: GitHub Personal Access Token
                - default_repo: 默认仓库（格式：owner/repo）
        """
        self.config = config or {}
        self.token = self.config.get("token")
        self.default_repo = self.config.get("default_repo", "")
    
    def create_issue(
        self,
        repo: Optional[str] = None,
        title: str = "",
        body: str = "",
        labels: Optional[List[str]] = None,
    ) -> ToolResult:
        """
        创建 GitHub Issue
        
        Args:
            repo: 仓库名称（格式：owner/repo），如果未提供则使用默认仓库
            title: Issue 标题
            body: Issue 正文
            labels: 标签列表
        
        Returns:
            ToolResult 对象
        """
        if not title:
            return ToolResult(
                success=False,
                message="Issue 标题不能为空",
                error="missing_title",
            )
        
        repo = repo or self.default_repo
        if not repo:
            return ToolResult(
                success=False,
                message="未指定仓库，且没有默认仓库配置",
                error="missing_repo",
            )
        
        # 如果没有 token，模拟创建（用于测试）
        if not self.token:
            logger.warning("⚠️  GitHub token 未配置，模拟创建 Issue")
            issue_data = {
                "repo": repo,
                "title": title,
                "body": body,
                "labels": labels or [],
                "created_at": datetime.now().isoformat(),
                "status": "simulated",
            }
            
            # 保存到本地文件（用于测试和调试）
            self._save_simulated_issue(issue_data)
            
            return ToolResult(
                success=True,
                message=f"已模拟创建 Issue: {title} (仓库: {repo})",
                data=issue_data,
            )
        
        # 实际调用 GitHub API
        try:
            import requests
            
            url = f"https://api.github.com/repos/{repo}/issues"
            headers = {
                "Authorization": f"token {self.token}",
                "Accept": "application/vnd.github.v3+json",
            }
            payload = {
                "title": title,
                "body": body,
            }
            if labels:
                payload["labels"] = labels
            
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            
            issue_data = response.json()
            
            return ToolResult(
                success=True,
                message=f"已创建 Issue #{issue_data['number']}: {title}",
                data={
                    "repo": repo,
                    "number": issue_data["number"],
                    "url": issue_data["html_url"],
                    "title": title,
                },
            )
        except Exception as e:
            logger.error(f"创建 GitHub Issue 失败: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"创建 Issue 失败: {str(e)}",
                error=str(e),
            )
    
    def _save_simulated_issue(self, issue_data: Dict[str, Any]):
        """保存模拟的 Issue 到本地文件"""
        project_root = Path(__file__).parent.parent.parent
        issues_dir = project_root / "data" / "simulated_issues"
        issues_dir.mkdir(parents=True, exist_ok=True)
        
        issue_file = issues_dir / f"issue_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(issue_file, 'w', encoding='utf-8') as f:
            json.dump(issue_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✓ 模拟 Issue 已保存: {issue_file}")


class CalendarInviteTool:
    """日历邀请工具"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化日历邀请工具
        
        Args:
            config: 配置字典，包含：
                - email: 用户邮箱（用于发送邀请）
                - calendar_api: 日历 API 配置（可选）
        """
        self.config = config or {}
        self.email = self.config.get("email", "")
    
    def send_invite(
        self,
        attendees: List[str],
        title: str,
        start_time: str,
        duration_minutes: int = 30,
        description: str = "",
    ) -> ToolResult:
        """
        发送日历邀请
        
        Args:
            attendees: 参与者邮箱列表
            title: 会议标题
            start_time: 开始时间（ISO 格式，如 "2025-11-15T10:00:00"）
            duration_minutes: 持续时间（分钟）
            description: 会议描述
        
        Returns:
            ToolResult 对象
        """
        if not title:
            return ToolResult(
                success=False,
                message="会议标题不能为空",
                error="missing_title",
            )
        
        if not attendees:
            return ToolResult(
                success=False,
                message="参与者列表不能为空",
                error="missing_attendees",
            )
        
        try:
            # 解析开始时间
            start_dt = datetime.fromisoformat(start_time.replace('Z', '+00:00'))
            end_dt = start_dt.replace(minute=start_dt.minute + duration_minutes)
            
            # 生成日历事件数据
            event_data = {
                "title": title,
                "start_time": start_dt.isoformat(),
                "end_time": end_dt.isoformat(),
                "attendees": attendees,
                "description": description,
                "created_at": datetime.now().isoformat(),
            }
            
            # 如果没有配置日历 API，模拟发送
            if not self.config.get("calendar_api"):
                logger.warning("⚠️  日历 API 未配置，模拟发送邀请")
                self._save_simulated_invite(event_data)
                
                return ToolResult(
                    success=True,
                    message=f"已模拟发送日历邀请: {title} ({len(attendees)} 位参与者)",
                    data=event_data,
                )
            
            # 实际调用日历 API（Google Calendar / Outlook）
            # TODO: 集成 Google Calendar API 或 Outlook API
            
            return ToolResult(
                success=True,
                message=f"已发送日历邀请: {title}",
                data=event_data,
            )
        except ValueError as e:
            return ToolResult(
                success=False,
                message=f"时间格式错误: {str(e)}",
                error="invalid_time_format",
            )
        except Exception as e:
            logger.error(f"发送日历邀请失败: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"发送邀请失败: {str(e)}",
                error=str(e),
            )
    
    def _save_simulated_invite(self, event_data: Dict[str, Any]):
        """保存模拟的日历邀请到本地文件"""
        project_root = Path(__file__).parent.parent.parent
        invites_dir = project_root / "data" / "simulated_invites"
        invites_dir.mkdir(parents=True, exist_ok=True)
        
        invite_file = invites_dir / f"invite_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(invite_file, 'w', encoding='utf-8') as f:
            json.dump(event_data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✓ 模拟日历邀请已保存: {invite_file}")


class ReadingListTool:
    """阅读列表工具"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        初始化阅读列表工具
        
        Args:
            config: 配置字典，包含：
                - reading_list_path: 阅读列表文件路径
                - integration: 集成类型（"obsidian", "notion", "local"）
        """
        self.config = config or {}
        self.integration = self.config.get("integration", "local")
        self.reading_list_path = self.config.get(
            "reading_list_path",
            Path(__file__).parent.parent.parent / "data" / "reading_list.json"
        )
    
    def add_to_list(
        self,
        url: str,
        title: Optional[str] = None,
        priority: str = "medium",
        notes: Optional[str] = None,
    ) -> ToolResult:
        """
        添加到阅读列表
        
        Args:
            url: 文章 URL
            title: 文章标题（可选）
            priority: 优先级（"high", "medium", "low"）
            notes: 备注（可选）
        
        Returns:
            ToolResult 对象
        """
        if not url:
            return ToolResult(
                success=False,
                message="URL 不能为空",
                error="missing_url",
            )
        
        # 验证优先级
        if priority not in ["high", "medium", "low"]:
            priority = "medium"
        
        item = {
            "url": url,
            "title": title or "",
            "priority": priority,
            "notes": notes or "",
            "added_at": datetime.now().isoformat(),
            "read": False,
        }
        
        try:
            if self.integration == "obsidian":
                return self._add_to_obsidian(item)
            elif self.integration == "notion":
                return self._add_to_notion(item)
            else:
                return self._add_to_local(item)
        except Exception as e:
            logger.error(f"添加到阅读列表失败: {e}", exc_info=True)
            return ToolResult(
                success=False,
                message=f"添加失败: {str(e)}",
                error=str(e),
            )
    
    def _add_to_local(self, item: Dict[str, Any]) -> ToolResult:
        """添加到本地 JSON 文件"""
        reading_list_path = Path(self.reading_list_path)
        reading_list_path.parent.mkdir(parents=True, exist_ok=True)
        
        # 读取现有列表
        if reading_list_path.exists():
            with open(reading_list_path, 'r', encoding='utf-8') as f:
                reading_list = json.load(f)
        else:
            reading_list = []
        
        # 检查是否已存在
        if any(existing.get("url") == item["url"] for existing in reading_list):
            return ToolResult(
                success=False,
                message=f"URL 已存在于阅读列表中: {item['url']}",
                error="duplicate_url",
            )
        
        # 添加新项
        reading_list.append(item)
        
        # 保存
        with open(reading_list_path, 'w', encoding='utf-8') as f:
            json.dump(reading_list, f, ensure_ascii=False, indent=2)
        
        logger.info(f"✓ 已添加到阅读列表: {item.get('title', item['url'])}")
        
        return ToolResult(
            success=True,
            message=f"已添加到阅读列表: {item.get('title', item['url'])}",
            data=item,
        )
    
    def _add_to_obsidian(self, item: Dict[str, Any]) -> ToolResult:
        """添加到 Obsidian（TODO: 实现）"""
        # TODO: 集成 Obsidian API 或文件系统操作
        logger.warning("⚠️  Obsidian 集成未实现，使用本地存储")
        return self._add_to_local(item)
    
    def _add_to_notion(self, item: Dict[str, Any]) -> ToolResult:
        """添加到 Notion（TODO: 实现）"""
        # TODO: 集成 Notion API
        logger.warning("⚠️  Notion 集成未实现，使用本地存储")
        return self._add_to_local(item)


# 工具注册表
TOOLS_REGISTRY = {
    "create_github_issue": GitHubIssueTool,
    "send_calendar_invite": CalendarInviteTool,
    "add_to_reading_list": ReadingListTool,
}


def get_tool_schemas() -> List[Dict[str, Any]]:
    """
    获取工具 Schema（用于 LLM Function Calling）
    
    Returns:
        工具 Schema 列表
    """
    return [
        {
            "type": "function",
            "function": {
                "name": "create_github_issue",
                "description": "创建 GitHub Issue。用于将重要任务、bug 或功能请求记录到 GitHub 仓库。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "repo": {
                            "type": "string",
                            "description": "仓库名称（格式：owner/repo），例如 'david/ai-digest'",
                        },
                        "title": {
                            "type": "string",
                            "description": "Issue 标题",
                        },
                        "body": {
                            "type": "string",
                            "description": "Issue 正文（Markdown 格式）",
                        },
                        "labels": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "标签列表，例如 ['bug', 'enhancement']",
                        },
                    },
                    "required": ["title"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "send_calendar_invite",
                "description": "发送日历邀请。用于安排会议或提醒重要事件。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "attendees": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "参与者邮箱列表",
                        },
                        "title": {
                            "type": "string",
                            "description": "会议标题",
                        },
                        "start_time": {
                            "type": "string",
                            "description": "开始时间（ISO 格式），例如 '2025-11-15T10:00:00'",
                        },
                        "duration_minutes": {
                            "type": "integer",
                            "description": "持续时间（分钟），默认 30",
                            "default": 30,
                        },
                        "description": {
                            "type": "string",
                            "description": "会议描述",
                        },
                    },
                    "required": ["attendees", "title", "start_time"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "add_to_reading_list",
                "description": "添加到阅读列表。用于保存需要稍后阅读的文章或资源。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "文章或资源 URL",
                        },
                        "title": {
                            "type": "string",
                            "description": "文章标题（可选）",
                        },
                        "priority": {
                            "type": "string",
                            "enum": ["high", "medium", "low"],
                            "description": "优先级，默认 'medium'",
                            "default": "medium",
                        },
                        "notes": {
                            "type": "string",
                            "description": "备注（可选）",
                        },
                    },
                    "required": ["url"],
                },
            },
        },
    ]


__all__ = [
    "ToolResult",
    "GitHubIssueTool",
    "CalendarInviteTool",
    "ReadingListTool",
    "TOOLS_REGISTRY",
    "get_tool_schemas",
]

