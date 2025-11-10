"""
Unit tests for collectors
采集器的单元测试
"""

import pytest
from datetime import datetime, timedelta
from src.collectors.rss_collector import RSSCollector, RSSItem
from src.collectors.github_collector import GitHubCollector, GitHubRelease


class TestRSSCollector:
    """RSS采集器测试"""
    
    def test_rss_collector_init(self):
        """测试初始化"""
        sources = [
            {'name': 'Test Blog', 'url': 'https://example.com/rss', 'category': 'test', 'priority': 5}
        ]
        collector = RSSCollector(sources)
        assert collector.sources == sources
        assert len(collector.items) == 0
    
    def test_parse_date(self):
        """测试日期解析"""
        sources = []
        collector = RSSCollector(sources)
        
        # 测试有published_parsed的情况
        class MockEntry:
            published_parsed = (2024, 1, 1, 12, 0, 0, 0, 1, 0)
        
        entry = MockEntry()
        result = collector._parse_date(entry)
        assert isinstance(result, datetime)
        assert result.year == 2024


class TestGitHubCollector:
    """GitHub采集器测试"""
    
    def test_github_collector_init(self):
        """测试初始化"""
        repos = [
            {'name': 'Test Repo', 'repo': 'test/repo', 'category': 'test', 'priority': 5}
        ]
        collector = GitHubCollector(repos)
        assert collector.repos_config == repos
        assert len(collector.releases) == 0
    
    def test_clean_description(self):
        """测试描述清理"""
        repos = []
        collector = GitHubCollector(repos)
        
        # 测试长描述截断
        long_desc = "a" * 2000
        result = collector._clean_description(long_desc, max_length=1000)
        assert len(result) <= 1003  # 1000 + "..."
        
        # 测试空行移除
        desc_with_blank = "Line 1\n\n\nLine 2\n\n"
        result = collector._clean_description(desc_with_blank)
        assert "Line 1\nLine 2" in result


def test_integration_example():
    """集成测试示例（需要网络连接）"""
    # 这个测试需要实际的网络请求，标记为skip
    pytest.skip("需要网络连接和API密钥")

