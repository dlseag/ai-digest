"""
Hacker News Collector
采集Hacker News上的AI相关热门故事
"""

import logging
import requests
from datetime import datetime, timedelta
from typing import List, Dict
from dataclasses import dataclass

from src.utils.dedupe import normalize_url, unique_items

logger = logging.getLogger(__name__)


@dataclass
class HackerNewsItem:
    """Hacker News条目数据类"""
    title: str
    link: str
    summary: str
    published: datetime
    source: str
    category: str
    priority: int
    points: int
    comments: int


class HackerNewsCollector:
    """Hacker News采集器"""
    
    def __init__(self, query_tags: List[str], min_points: int = 50):
        """
        初始化HN采集器
        
        Args:
            query_tags: 搜索关键词列表
            min_points: 最低点赞数（过滤噪音）
        """
        self.query_tags = query_tags
        self.min_points = min_points
        self.base_url = "https://hn.algolia.com/api/v1/search"
        
    def collect(self, days_back: int = 7) -> List[HackerNewsItem]:
        """
        采集AI相关的热门故事
        
        Args:
            days_back: 采集最近N天的内容
            
        Returns:
            HN条目列表
        """
        items = []
        cutoff_timestamp = int((datetime.now() - timedelta(days=days_back)).timestamp())
        
        try:
            # 为每个关键词搜索
            for tag in self.query_tags:
                tag_items = self._search_by_tag(tag, cutoff_timestamp)
                items.extend(tag_items)
            
            # 去重（基于规范化URL）
            unique_items_list = unique_items(
                items, lambda item: normalize_url(item.link) or item.title
            )
            
            # 按点数排序
            unique_items_list.sort(key=lambda x: x.points, reverse=True)
            
            logger.info(f"✓ 采集 Hacker News: {len(unique_items_list)} 条目")
            return unique_items_list
            
        except Exception as e:
            logger.error(f"HackerNews采集失败: {str(e)}")
            return []
    
    def _search_by_tag(self, tag: str, cutoff_timestamp: int) -> List[HackerNewsItem]:
        """
        搜索单个关键词
        
        Args:
            tag: 关键词
            cutoff_timestamp: 时间戳截止点
            
        Returns:
            条目列表
        """
        items = []
        
        try:
            params = {
                'query': tag,
                'tags': 'story',
                'numericFilters': f'created_at_i>{cutoff_timestamp},points>{self.min_points}',
                'hitsPerPage': 20
            }
            
            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()
            
            for hit in data.get('hits', []):
                # 提取数据
                title = hit.get('title', '')
                url = hit.get('url') or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
                
                # 创建摘要（使用文章文本或评论）
                summary = self._create_summary(hit)
                
                # 解析时间
                created_at = hit.get('created_at_i', 0)
                published = datetime.fromtimestamp(created_at) if created_at else datetime.now()
                
                item = HackerNewsItem(
                    title=title,
                    link=url,
                    summary=summary,
                    published=published,
                    source="Hacker News",
                    category="community",
                    priority=9,
                    points=hit.get('points', 0),
                    comments=hit.get('num_comments', 0)
                )
                items.append(item)
                
        except Exception as e:
            logger.warning(f"搜索HN标签'{tag}'失败: {str(e)}")
        
        return items
    
    def _create_summary(self, hit: Dict) -> str:
        """
        创建摘要文本
        
        Args:
            hit: HN API返回的hit对象
            
        Returns:
            摘要文本
        """
        # 优先使用story_text，否则使用标题
        text = hit.get('story_text') or hit.get('comment_text') or ''
        
        if text:
            # 清理HTML
            from bs4 import BeautifulSoup
            text = BeautifulSoup(text, 'html.parser').get_text()
            # 限制长度
            if len(text) > 300:
                text = text[:300] + "..."
        else:
            # 如果没有文本，使用标题 + 元数据
            points = hit.get('points', 0)
            comments = hit.get('num_comments', 0)
            text = f"热门讨论：{points}分，{comments}条评论"
        
        return text

