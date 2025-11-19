"""
RSS Feed Collector
RSS订阅采集器，用于收集官方博客更新
"""

import feedparser
import logging
import signal
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
import requests
from bs4 import BeautifulSoup

from src.collectors.html_parsers import get_html_parser
from src.collectors.retry_handler import RetryHandler, SourceHealthTracker
from src.utils.dedupe import normalize_url, unique_items

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
        # 快速失败策略：减少重试次数和延迟
        self.retry_handler = RetryHandler(max_retries=1, base_delay=0.5, max_delay=2.0)
        self.health_tracker = SourceHealthTracker()
        
    def collect_all(self, days_back: int = 7, source_timeout: float = 15.0) -> List[RSSItem]:
        """
        采集所有RSS源的最新内容
        
        Args:
            days_back: 采集最近N天的内容，默认7天
            source_timeout: 每个源的最大采集时间（秒），默认30秒
            
        Returns:
            采集到的RSS条目列表
        """
        cutoff_date = datetime.now() - timedelta(days=days_back)
        all_items = []
        skipped_count = 0
        
        @contextmanager
        def timeout_context(seconds):
            """为单个源设置超时上下文"""
            def timeout_handler(signum, frame):
                raise TimeoutError(f"源采集超时（{seconds}秒）")
            
            # 设置信号处理器（仅Unix系统）
            if hasattr(signal, 'SIGALRM'):
                old_handler = signal.signal(signal.SIGALRM, timeout_handler)
                signal.alarm(int(seconds))
                try:
                    yield
                finally:
                    signal.alarm(0)
                    signal.signal(signal.SIGALRM, old_handler)
            else:
                # Windows系统不支持SIGALRM，使用简单的超时
                yield
        
        for source in self.sources:
            # 检查源是否健康
            if not self.health_tracker.is_healthy(source['name'], source['url']):
                skipped_count += 1
                logger.debug(f"⏭ 跳过不健康的数据源: {source['name']}")
                continue
            
            try:
                # 为每个源设置超时
                try:
                    if hasattr(signal, 'SIGALRM'):
                        # Unix系统使用信号超时
                        with timeout_context(source_timeout):
                            items = self._collect_source(source, cutoff_date)
                    else:
                        # Windows系统直接调用（依赖requests的timeout）
                        items = self._collect_source(source, cutoff_date)
                except TimeoutError as e:
                    logger.warning(f"⏱ {source['name']}: {str(e)}")
                    self.health_tracker.record_failure(
                        source['name'],
                        source['url'],
                        error_type='TimeoutError',
                        error_message=str(e)
                    )
                    continue
                
                all_items.extend(items)
                
                # 记录成功
                if items:
                    self.health_tracker.record_success(source['name'], source['url'])
                    logger.info(f"✓ 采集 {source['name']}: {len(items)} 条目")
                else:
                    logger.debug(f"⚠ {source['name']}: 无新条目")
                    
            except requests.exceptions.HTTPError as e:
                # HTTP 错误（404, 500等）
                status_code = e.response.status_code if e.response else None
                error_msg = str(e)
                
                self.health_tracker.record_failure(
                    source['name'],
                    source['url'],
                    error_type='HTTPError',
                    error_message=error_msg,
                    status_code=status_code
                )
                
                if status_code == 404:
                    logger.warning(f"✗ {source['name']}: 404 Not Found (可能已失效)")
                else:
                    logger.error(f"✗ {source['name']}: HTTP {status_code} - {error_msg}")
                    
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                # 网络错误
                error_type = type(e).__name__
                error_msg = str(e)
                
                self.health_tracker.record_failure(
                    source['name'],
                    source['url'],
                    error_type=error_type,
                    error_message=error_msg
                )
                
                logger.error(f"✗ {source['name']}: 网络错误 ({error_type}) - {error_msg}")
                
            except Exception as e:
                # 其他错误
                error_msg = str(e)
                
                self.health_tracker.record_failure(
                    source['name'],
                    source['url'],
                    error_type=type(e).__name__,
                    error_message=error_msg
                )
                
                logger.error(f"✗ 采集失败 {source['name']}: {error_msg}")
        
        unique_items_list = unique_items(
            all_items,
            lambda item: normalize_url(item.link) or normalize_url(item.title),
        )
        unique_items_list.sort(key=lambda x: x.published, reverse=True)
        
        self.items = unique_items_list
        
        # 记录统计信息
        health_summary = self.health_tracker.get_health_summary()
        logger.info(f"总共采集 {len(unique_items_list)} 条RSS条目 (跳过 {skipped_count} 个不健康源)")
        if health_summary['unhealthy'] > 0:
            logger.warning(f"⚠ 有 {health_summary['unhealthy']} 个数据源标记为不健康")
        
        return unique_items_list
    
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
        
        # 检查是否需要 HTML 解析（无 RSS feed）
        parser_hint = source.get('html_parser')
        if parser_hint and parser_hint != 'auto':
            requires_html_parsing = True
        else:
            url_lower = source['url'].lower()
            looks_like_feed = any(
                keyword in url_lower
                for keyword in ['rss', 'feed', 'atom', '.xml', '.rss']
            ) or url_lower.endswith('.xml')
            requires_html_parsing = not looks_like_feed
        
        if requires_html_parsing:
            return self._collect_html_source(source, cutoff_date)
        
        # 标准RSS采集（使用重试机制）
        def fetch_feed():
            """获取 RSS feed（带重试，快速失败）"""
            session = self.retry_handler.create_session(timeout=8.0)
            response = session.get(source['url'], timeout=(5, 8))  # 连接5秒，读取8秒
            response.raise_for_status()
            return feedparser.parse(response.content)
        
        try:
            feed, error = self.retry_handler.retry_with_backoff(fetch_feed)
            
            if error:
                # 重试失败，抛出异常
                raise error
            
            # 检查 feed 是否有效
            if feed.bozo and feed.bozo_exception:
                logger.warning(f"RSS feed 解析警告 {source['name']}: {feed.bozo_exception}")
                # 如果 RSS 无效，尝试 HTML 解析作为降级方案
                if not feed.entries:
                    logger.info(f"RSS feed 无效，尝试 HTML 解析: {source['name']}")
                    return self._collect_html_source(source, cutoff_date)
            
            for entry in feed.entries:
                # 解析发布日期
                published = self._parse_date(entry)
                
                # 过滤旧内容
                if published and published < cutoff_date:
                    continue
                
                # 对于日期解析失败的条目（published=None），采用保守策略
                # arXiv 的 RSS feed 每天更新，所以无日期的论文可以认为是"今天"的
                # 但为了避免误采集，我们只保留论文类别的无日期条目
                if published is None:
                    if source.get('category') != 'paper':
                        # 非论文类别，日期解析失败则跳过（避免采集旧新闻）
                        logger.debug(f"跳过无日期条目（非论文）: {entry.get('title', '')[:50]}")
                        continue
                    # 论文类别，使用当前时间（arXiv RSS 每天更新，可认为是今天的）
                    published = datetime.now()
                
                # 提取摘要
                summary = self._extract_summary(entry)
                
                # 创建条目
                item = RSSItem(
                    title=entry.get('title', ''),
                    link=entry.get('link', ''),
                    summary=summary,
                    published=published,
                    source=source['name'],
                    category=source['category'],
                    priority=source['priority'],
                    content=entry.get('content', [{}])[0].get('value', '') if 'content' in entry else None
                )
                items.append(item)
                
        except requests.exceptions.HTTPError as e:
            # HTTP 错误，重新抛出以便上层处理
            raise
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
            # 网络错误，重新抛出以便上层处理
            raise
        except Exception as e:
            logger.error(f"解析RSS失败 {source['name']}: {str(e)}")
            # RSS 解析失败时，尝试 HTML 解析作为降级方案
            logger.info(f"尝试 HTML 解析作为降级方案: {source['name']}")
            try:
                return self._collect_html_source(source, cutoff_date)
            except Exception as html_error:
                logger.error(f"HTML 解析也失败 {source['name']}: {str(html_error)}")
                raise  # 重新抛出异常以便上层记录失败
            
        return items
    
    def _collect_html_source(self, source: Dict, cutoff_date: datetime) -> List[RSSItem]:
        """
        使用 HTML 解析器采集无 RSS feed 的源
        
        Args:
            source: 源配置
            cutoff_date: 截止日期
            
        Returns:
            RSSItem 列表
        """
        items = []
        
        # 使用重试机制获取 HTML
        def fetch_html():
            """获取 HTML 内容（带重试，快速失败）"""
            session = self.retry_handler.create_session(timeout=8.0)
            return session.get(source['url'], timeout=(5, 8))  # 连接5秒，读取8秒
        
        try:
            response, error = self.retry_handler.retry_with_backoff(fetch_html)
            
            if error:
                raise error
            
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # 获取合适的解析器
            parser_type = source.get('html_parser', 'auto')
            if parser_type == 'auto':
                parser = get_html_parser(source['name'], source['url'])
            else:
                from src.collectors.html_parsers import _parser_registry
                parser = _parser_registry.get_parser(parser_type, source['url'])
            
            # 解析文章
            articles = parser.parse(soup, source['url'])
            
            for article_data in articles:
                try:
                    # 检查日期（如果可用）
                    published = article_data.get('published_date')
                    if published and published < cutoff_date:
                        continue
                    
                    item = RSSItem(
                        title=article_data.get('title', ''),
                        link=article_data.get('link', ''),
                        summary=article_data.get('summary', ''),
                        published=published or datetime.now(),
                        source=source['name'],
                        category=source['category'],
                        priority=source['priority']
                    )
                    items.append(item)
                    
                except Exception as e:
                    logger.debug(f"解析文章失败 ({source['name']}): {str(e)}")
                    continue
            
            if items:
                logger.info(f"✓ HTML 解析成功 {source['name']}: {len(items)} 条目")
            else:
                logger.warning(f"⚠ HTML 解析未找到文章 {source['name']}")
                    
        except requests.exceptions.RequestException as e:
            logger.error(f"访问失败 {source['name']}: {str(e)}")
        except Exception as e:
            logger.error(f"HTML 解析失败 {source['name']}: {str(e)}")
            
        return items[:10]  # 最多返回10篇
    
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

