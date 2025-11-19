"""
Tests for Report Generator - Must-Read Selection Logic
测试报告生成器的"必看内容"筛选逻辑
"""

import pytest
from unittest.mock import Mock
from src.generators.report_generator import ReportGenerator


class TestMustReadSelection:
    """测试"必看内容"筛选逻辑"""
    
    @pytest.fixture
    def generator(self):
        """创建报告生成器实例"""
        return ReportGenerator()
    
    @pytest.fixture
    def mock_items(self):
        """创建模拟的处理后条目"""
        items = []
        
        # 创建5个arXiv论文（高优先级）
        for i in range(5):
            item = Mock()
            item.title = f"arXiv Paper {i}"
            item.url = f"https://arxiv.org/abs/2511.0{i}000"
            item.source = f"arXiv cs.AI"
            item.personal_priority = 9
            item.relevance_score = 9
            item.is_release = False
            item.promote_release = False
            items.append(item)
        
        # 创建2个Reddit帖子（高优先级）
        for i in range(2):
            item = Mock()
            item.title = f"Reddit Post {i}"
            item.url = f"https://www.reddit.com/r/LocalLLaMA/comments/{i}"
            item.source = "Reddit r/LocalLLaMA"
            item.personal_priority = 9
            item.relevance_score = 9
            item.is_release = False
            item.promote_release = False
            items.append(item)
        
        # 创建1个Simon Willison博客（高优先级）
        item = Mock()
        item.title = "Simon Willison Blog Post"
        item.url = "https://simonwillison.net/2025/Nov/12/test/"
        item.source = "Simon Willison"
        item.personal_priority = 9
        item.relevance_score = 9
        item.is_release = False
        item.promote_release = False
        items.append(item)
        
        # 创建1个Hacker News讨论（高优先级）
        item = Mock()
        item.title = "Hacker News Discussion"
        item.url = "https://news.ycombinator.com/item?id=12345"
        item.source = "Hacker News"
        item.personal_priority = 9
        item.relevance_score = 9
        item.is_release = False
        item.promote_release = False
        items.append(item)
        
        return items
    
    def test_arxiv_limit(self, generator, mock_items):
        """测试arXiv论文数量限制（最多2条）"""
        # 调用内部方法进行筛选
        sorted_items = sorted(
            mock_items,
            key=lambda x: x.personal_priority,
            reverse=True
        )
        
        must_read_items = []
        source_counts = {}
        max_per_source = 2
        used_keys = set()
        
        for item in sorted_items:
            if item.personal_priority < 8:
                continue
            if item.is_release and not item.promote_release:
                continue
            
            dedupe_key = generator._make_dedupe_key(item)
            if dedupe_key in used_keys:
                continue
            
            source_key = generator._normalize_source(item.source)
            
            # 限制arXiv论文数量（最多2条）
            arxiv_count = sum(1 for s in source_counts.keys() if 'arxiv' in s.lower())
            if 'arxiv' in source_key.lower() and arxiv_count >= max_per_source:
                continue
            
            # 限制同一来源的数量
            if source_counts.get(source_key, 0) >= max_per_source:
                continue
            
            must_read_items.append(item)
            used_keys.add(dedupe_key)
            source_counts[source_key] = source_counts.get(source_key, 0) + 1
            
            if len(must_read_items) >= 5:
                break
        
        # 验证结果
        arxiv_items = [item for item in must_read_items if 'arxiv' in item.source.lower()]
        assert len(arxiv_items) <= 2, f"arXiv条目数量应该<=2，实际为{len(arxiv_items)}"
    
    def test_source_diversity(self, generator, mock_items):
        """测试来源多样性（不应全部来自同一来源）"""
        sorted_items = sorted(
            mock_items,
            key=lambda x: x.personal_priority,
            reverse=True
        )
        
        must_read_items = []
        source_counts = {}
        max_per_source = 2
        used_keys = set()
        
        for item in sorted_items:
            if item.personal_priority < 8:
                continue
            if item.is_release and not item.promote_release:
                continue
            
            dedupe_key = generator._make_dedupe_key(item)
            if dedupe_key in used_keys:
                continue
            
            source_key = generator._normalize_source(item.source)
            
            arxiv_count = sum(1 for s in source_counts.keys() if 'arxiv' in s.lower())
            if 'arxiv' in source_key.lower() and arxiv_count >= max_per_source:
                continue
            
            if source_counts.get(source_key, 0) >= max_per_source:
                continue
            
            must_read_items.append(item)
            used_keys.add(dedupe_key)
            source_counts[source_key] = source_counts.get(source_key, 0) + 1
            
            if len(must_read_items) >= 5:
                break
        
        # 验证来源多样性
        unique_sources = set(generator._normalize_source(item.source) for item in must_read_items)
        assert len(unique_sources) >= 2, f"必看内容应包含至少2个不同来源，实际为{len(unique_sources)}"
    
    def test_normalize_source(self, generator):
        """测试来源名称标准化"""
        assert generator._normalize_source("arXiv cs.AI") == "arxiv"
        assert generator._normalize_source("arXiv cs.CL") == "arxiv"
        assert generator._normalize_source("Reddit r/LocalLLaMA") == "reddit"
        assert generator._normalize_source("Hacker News") == "hacker_news"
        assert generator._normalize_source("Simon Willison") == "Simon"
    
    def test_priority_threshold(self, generator):
        """测试优先级阈值（>=8分）"""
        items = []
        
        # 创建高优先级条目
        high_item = Mock()
        high_item.title = "High Priority Item"
        high_item.url = "https://example.com/high"
        high_item.source = "Test Source"
        high_item.personal_priority = 9
        high_item.relevance_score = 9
        high_item.is_release = False
        high_item.promote_release = False
        items.append(high_item)
        
        # 创建低优先级条目
        low_item = Mock()
        low_item.title = "Low Priority Item"
        low_item.url = "https://example.com/low"
        low_item.source = "Test Source"
        low_item.personal_priority = 7
        low_item.relevance_score = 7
        low_item.is_release = False
        low_item.promote_release = False
        items.append(low_item)
        
        sorted_items = sorted(items, key=lambda x: x.personal_priority, reverse=True)
        
        must_read_items = []
        used_keys = set()
        
        for item in sorted_items:
            if item.personal_priority < 8:
                continue
            if item.is_release and not item.promote_release:
                continue
            
            dedupe_key = generator._make_dedupe_key(item)
            if dedupe_key in used_keys:
                continue
            
            must_read_items.append(item)
            used_keys.add(dedupe_key)
        
        assert len(must_read_items) == 1, "只有高优先级条目应该被选中"
        assert must_read_items[0].personal_priority >= 8


class TestDedupe:
    """测试去重逻辑"""
    
    @pytest.fixture
    def generator(self):
        return ReportGenerator()
    
    def test_dedupe_by_url(self, generator):
        """测试基于URL的去重"""
        item1 = Mock()
        item1.title = "Same Item"
        item1.url = "https://example.com/article"
        item1.link = None
        
        item2 = Mock()
        item2.title = "Same Item"
        item2.url = "https://example.com/article"
        item2.link = None
        
        key1 = generator._make_dedupe_key(item1)
        key2 = generator._make_dedupe_key(item2)
        
        assert key1 == key2, "相同URL的条目应该生成相同的去重键"
    
    def test_dedupe_by_title(self, generator):
        """测试基于标题的去重（当URL为空时）"""
        item1 = Mock()
        item1.title = "Unique Title"
        item1.url = None
        item1.link = None
        
        item2 = Mock()
        item2.title = "Unique Title"
        item2.url = None
        item2.link = None
        
        key1 = generator._make_dedupe_key(item1)
        key2 = generator._make_dedupe_key(item2)
        
        assert key1 == key2, "相同标题的条目应该生成相同的去重键"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

