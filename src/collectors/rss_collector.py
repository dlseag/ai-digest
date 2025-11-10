"""
RSS Feed Collector
RSS订阅采集器，用于收集官方博客更新
"""

import feedparser
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class RSSItem:
    """RSS条目数据类"""
    title: str
    link: str
    summary: str
    published: datetime
    source: str
    category: str
    priority: int
    content: Optional[str] = None


class RSSCollector:
    """RSS订阅采集器"""
    
    def __init__(self, sources_config: List[Dict]):
        """
        初始化RSS采集器
        
        Args:
            sources_config: RSS源配置列表
        """
        self.sources = sources_config
        self.items: List[RSSItem] = []
        
    def collect_all(self, days_back: int = 7) -> List[RSSItem]:
        """
        采集所有RSS源的最新内容
        
        Args:
            days_back: 采集最近N天的内容，默认7天
            
        Returns:
            采集到的RSS条目列表
        """
        cutoff_date = datetime.now() - timedelta(days=days_back)
        all_items = []
        
        for source in self.sources:
            try:
                items = self._collect_source(source, cutoff_date)
                all_items.extend(items)
                logger.info(f"✓ 采集 {source['name']}: {len(items)} 条目")
            except Exception as e:
                logger.error(f"✗ 采集失败 {source['name']}: {str(e)}")
                
        # 按发布时间倒序排序
        all_items.sort(key=lambda x: x.published, reverse=True)
        
        self.items = all_items
        logger.info(f"总共采集 {len(all_items)} 条RSS条目")
        return all_items
    
    def _collect_source(self, source: Dict, cutoff_date: datetime) -> List[RSSItem]:
        """
        采集单个RSS源
        
        Args:
            source: RSS源配置
            cutoff_date: 截止日期，只采集此日期之后的内容
            
        Returns:
            该源的条目列表
        """
        items = []
        
        # 特殊处理：Anthropic没有RSS，需要自定义解析
        if "anthropic" in source['url'].lower() and "rss" not in source['url']:
            return self._collect_anthropic_blog(source, cutoff_date)
        
        # 标准RSS采集
        try:
            feed = feedparser.parse(source['url'])
            
            for entry in feed.entries:
                # 解析发布日期
                published = self._parse_date(entry)
                
                # 过滤旧内容
                if published and published < cutoff_date:
                    continue
                
                # 提取摘要
                summary = self._extract_summary(entry)
                
                # 创建条目
                item = RSSItem(
                    title=entry.get('title', ''),
                    link=entry.get('link', ''),
                    summary=summary,
                    published=published or datetime.now(),
                    source=source['name'],
                    category=source['category'],
                    priority=source['priority'],
                    content=entry.get('content', [{}])[0].get('value', '') if 'content' in entry else None
                )
                items.append(item)
                
        except Exception as e:
            logger.error(f"解析RSS失败 {source['name']}: {str(e)}")
            
        return items
    
    def _collect_anthropic_blog(self, source: Dict, cutoff_date: datetime) -> List[RSSItem]:
        """
        特殊处理：Anthropic博客（无RSS）
        
        这是一个简化版本，实际需要根据网站结构调整
        """
        items = []
        
        try:
            response = requests.get(source['url'], timeout=10)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # TODO: 根据实际网站结构调整选择器
            # 这里只是示例，可能需要调整
            articles = soup.find_all('article', limit=10)
            
            for article in articles:
                try:
                    title_elem = article.find('h2') or article.find('h3')
                    link_elem = article.find('a')
                    
                    if not title_elem or not link_elem:
                        continue
                    
                    title = title_elem.get_text().strip()
                    link = link_elem.get('href', '')
                    
                    # 处理相对链接
                    if link and not link.startswith('http'):
                        link = f"https://www.anthropic.com{link}"
                    
                    # 提取摘要
                    summary_elem = article.find('p')
                    summary = summary_elem.get_text().strip() if summary_elem else ""
                    
                    item = RSSItem(
                        title=title,
                        link=link,
                        summary=summary,
                        published=datetime.now(),  # 无法获取准确时间
                        source=source['name'],
                        category=source['category'],
                        priority=source['priority']
                    )
                    items.append(item)
                    
                except Exception as e:
                    logger.warning(f"解析Anthropic文章失败: {str(e)}")
                    
        except Exception as e:
            logger.error(f"访问Anthropic博客失败: {str(e)}")
            
        return items[:5]  # 最多返回5篇
    
    def _parse_date(self, entry) -> Optional[datetime]:
        """
        解析RSS条目的发布日期
        
        Args:
            entry: feedparser条目
            
        Returns:
            datetime对象，如果解析失败返回None
        """
        # 尝试多个可能的日期字段
        for date_field in ['published_parsed', 'updated_parsed', 'created_parsed']:
            if hasattr(entry, date_field):
                time_struct = getattr(entry, date_field)
                if time_struct:
                    try:
                        return datetime(*time_struct[:6])
                    except:
                        pass
        
        # 尝试字符串日期
        for date_field in ['published', 'updated', 'created']:
            if hasattr(entry, date_field):
                date_str = getattr(entry, date_field)
                if date_str:
                    try:
                        # 这里可以添加更复杂的日期解析逻辑
                        from dateutil import parser
                        return parser.parse(date_str)
                    except:
                        pass
        
        return None
    
    def _extract_summary(self, entry) -> str:
        """
        提取RSS条目的摘要
        
        Args:
            entry: feedparser条目
            
        Returns:
            摘要文本
        """
        # 尝试多个可能的摘要字段
        if hasattr(entry, 'summary') and entry.summary:
            summary = entry.summary
        elif hasattr(entry, 'description') and entry.description:
            summary = entry.description
        elif hasattr(entry, 'content') and entry.content:
            summary = entry.content[0].get('value', '')
        else:
            summary = ""
        
        # 清理HTML标签
        if summary:
            soup = BeautifulSoup(summary, 'html.parser')
            summary = soup.get_text().strip()
            
            # 限制长度
            if len(summary) > 500:
                summary = summary[:500] + "..."
        
        return summary
    
    def filter_by_keywords(self, keywords: List[str]) -> List[RSSItem]:
        """
        根据关键词过滤条目
        
        Args:
            keywords: 关键词列表
            
        Returns:
            包含关键词的条目列表
        """
        filtered = []
        
        for item in self.items:
            text = f"{item.title} {item.summary}".lower()
            if any(keyword.lower() in text for keyword in keywords):
                filtered.append(item)
        
        return filtered
    
    def get_top_priority(self, limit: int = 10) -> List[RSSItem]:
        """
        获取高优先级条目
        
        Args:
            limit: 返回数量限制
            
        Returns:
            按优先级排序的条目列表
        """
        sorted_items = sorted(self.items, key=lambda x: (-x.priority, x.published), reverse=True)
        return sorted_items[:limit]

