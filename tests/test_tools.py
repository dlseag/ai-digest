"""
测试工具调用框架
"""

import pytest
import json
from pathlib import Path
from datetime import datetime
from src.agents.tools import (
    ToolResult,
    GitHubIssueTool,
    CalendarInviteTool,
    ReadingListTool,
    get_tool_schemas,
)
from src.agents.tool_executor import ToolExecutor, parse_tool_calls_from_llm_response


class TestGitHubIssueTool:
    """测试 GitHub Issue 工具"""
    
    def test_create_issue_success(self, tmp_path):
        """测试成功创建 Issue（模拟模式）"""
        tool = GitHubIssueTool()
        
        result = tool.create_issue(
            repo="test/repo",
            title="Test Issue",
            body="This is a test issue",
        )
        
        assert result.success is True
        assert "Test Issue" in result.message
        assert result.data["repo"] == "test/repo"
        assert result.data["title"] == "Test Issue"
    
    def test_create_issue_missing_title(self):
        """测试缺少标题"""
        tool = GitHubIssueTool()
        
        result = tool.create_issue(repo="test/repo", title="")
        
        assert result.success is False
        assert "标题不能为空" in result.message
        assert result.error == "missing_title"
    
    def test_create_issue_missing_repo(self):
        """测试缺少仓库"""
        tool = GitHubIssueTool()
        
        result = tool.create_issue(title="Test Issue")
        
        assert result.success is False
        assert "未指定仓库" in result.message
    
    def test_create_issue_with_labels(self):
        """测试带标签创建 Issue"""
        tool = GitHubIssueTool()
        
        result = tool.create_issue(
            repo="test/repo",
            title="Test Issue",
            labels=["bug", "enhancement"],
        )
        
        assert result.success is True
        assert result.data["labels"] == ["bug", "enhancement"]


class TestCalendarInviteTool:
    """测试日历邀请工具"""
    
    def test_send_invite_success(self):
        """测试成功发送邀请（模拟模式）"""
        tool = CalendarInviteTool()
        
        result = tool.send_invite(
            attendees=["user@example.com"],
            title="Test Meeting",
            start_time="2025-11-15T10:00:00",
            duration_minutes=30,
        )
        
        assert result.success is True
        assert "Test Meeting" in result.message
        assert result.data["title"] == "Test Meeting"
        assert len(result.data["attendees"]) == 1
    
    def test_send_invite_missing_title(self):
        """测试缺少标题"""
        tool = CalendarInviteTool()
        
        result = tool.send_invite(
            attendees=["user@example.com"],
            title="",
            start_time="2025-11-15T10:00:00",
        )
        
        assert result.success is False
        assert "标题不能为空" in result.message
    
    def test_send_invite_missing_attendees(self):
        """测试缺少参与者"""
        tool = CalendarInviteTool()
        
        result = tool.send_invite(
            attendees=[],
            title="Test Meeting",
            start_time="2025-11-15T10:00:00",
        )
        
        assert result.success is False
        assert "参与者列表不能为空" in result.message
    
    def test_send_invite_invalid_time(self):
        """测试无效时间格式"""
        tool = CalendarInviteTool()
        
        result = tool.send_invite(
            attendees=["user@example.com"],
            title="Test Meeting",
            start_time="invalid-time",
        )
        
        assert result.success is False
        assert "时间格式错误" in result.message


class TestReadingListTool:
    """测试阅读列表工具"""
    
    @pytest.fixture
    def temp_reading_list(self, tmp_path):
        """创建临时阅读列表文件"""
        reading_list_path = tmp_path / "reading_list.json"
        return reading_list_path
    
    def test_add_to_list_success(self, temp_reading_list):
        """测试成功添加到阅读列表"""
        tool = ReadingListTool(config={"reading_list_path": str(temp_reading_list)})
        
        result = tool.add_to_list(
            url="https://example.com/article",
            title="Test Article",
            priority="high",
        )
        
        assert result.success is True
        assert "Test Article" in result.message
        assert result.data["url"] == "https://example.com/article"
        assert result.data["priority"] == "high"
        
        # 验证文件已创建
        assert temp_reading_list.exists()
        
        # 验证内容
        with open(temp_reading_list, 'r', encoding='utf-8') as f:
            reading_list = json.load(f)
        
        assert len(reading_list) == 1
        assert reading_list[0]["url"] == "https://example.com/article"
    
    def test_add_to_list_duplicate(self, temp_reading_list):
        """测试重复添加"""
        tool = ReadingListTool(config={"reading_list_path": str(temp_reading_list)})
        
        # 第一次添加
        result1 = tool.add_to_list(url="https://example.com/article")
        assert result1.success is True
        
        # 第二次添加（应该失败）
        result2 = tool.add_to_list(url="https://example.com/article")
        assert result2.success is False
        assert "已存在" in result2.message
    
    def test_add_to_list_missing_url(self):
        """测试缺少 URL"""
        tool = ReadingListTool()
        
        result = tool.add_to_list(url="")
        
        assert result.success is False
        assert "URL 不能为空" in result.message
    
    def test_add_to_list_invalid_priority(self, temp_reading_list):
        """测试无效优先级（应该使用默认值）"""
        tool = ReadingListTool(config={"reading_list_path": str(temp_reading_list)})
        
        result = tool.add_to_list(
            url="https://example.com/article",
            priority="invalid",
        )
        
        assert result.success is True
        assert result.data["priority"] == "medium"  # 默认值


class TestToolExecutor:
    """测试工具执行器"""
    
    def test_execute_github_issue(self):
        """测试执行 GitHub Issue 工具"""
        executor = ToolExecutor()
        
        result = executor.execute(
            "create_github_issue",
            {
                "repo": "test/repo",
                "title": "Test Issue",
                "body": "Test body",
            },
        )
        
        assert result.success is True
        assert "Test Issue" in result.message
    
    def test_execute_calendar_invite(self):
        """测试执行日历邀请工具"""
        executor = ToolExecutor()
        
        result = executor.execute(
            "send_calendar_invite",
            {
                "attendees": ["user@example.com"],
                "title": "Test Meeting",
                "start_time": "2025-11-15T10:00:00",
            },
        )
        
        assert result.success is True
        assert "Test Meeting" in result.message
    
    def test_execute_reading_list(self, tmp_path):
        """测试执行阅读列表工具"""
        reading_list_path = tmp_path / "reading_list.json"
        executor = ToolExecutor(config={
            "reading_list": {"reading_list_path": str(reading_list_path)}
        })
        
        result = executor.execute(
            "add_to_reading_list",
            {
                "url": "https://example.com/article",
                "title": "Test Article",
            },
        )
        
        assert result.success is True
        assert "Test Article" in result.message
    
    def test_execute_unknown_tool(self):
        """测试执行未知工具"""
        executor = ToolExecutor()
        
        result = executor.execute("unknown_tool", {})
        
        assert result.success is False
        assert "未知工具" in result.message
    
    def test_execute_batch(self, tmp_path):
        """测试批量执行"""
        reading_list_path = tmp_path / "reading_list.json"
        executor = ToolExecutor(config={
            "reading_list": {"reading_list_path": str(reading_list_path)}
        })
        
        tool_calls = [
            {
                "name": "add_to_reading_list",
                "arguments": {
                    "url": "https://example.com/article1",
                    "title": "Article 1",
                },
            },
            {
                "name": "add_to_reading_list",
                "arguments": {
                    "url": "https://example.com/article2",
                    "title": "Article 2",
                },
            },
        ]
        
        results = executor.execute_batch(tool_calls)
        
        assert len(results) == 2
        assert all(r.success for r in results)


class TestToolSchemas:
    """测试工具 Schema"""
    
    def test_get_tool_schemas(self):
        """测试获取工具 Schema"""
        schemas = get_tool_schemas()
        
        assert len(schemas) == 3
        
        # 验证每个工具都有正确的结构
        tool_names = {s["function"]["name"] for s in schemas}
        assert "create_github_issue" in tool_names
        assert "send_calendar_invite" in tool_names
        assert "add_to_reading_list" in tool_names
        
        # 验证 Schema 结构
        for schema in schemas:
            assert "type" in schema
            assert schema["type"] == "function"
            assert "function" in schema
            assert "name" in schema["function"]
            assert "description" in schema["function"]
            assert "parameters" in schema["function"]


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

