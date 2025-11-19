"""
News Collector
新闻采集器：从行业媒体RSS源采集AI新闻
"""

import feedparser
import requests
from datetime import datetime, timedelta
import logging
from typing import List, Dict

from src.collectors.retry_handler import RetryHandler, SourceHealthTracker

logger = logging.getLogger(__name__)


class NewsCollector:
    """行业新闻采集器"""
    
    def __init__(self, news_configs: List[Dict]):
        """
        初始化新闻采集器
        
        Args:
            news_configs: 新闻源配置列表，每个配置包含:
                - name: 新闻源名称
                - url: RSS URL
                - category: 分类
                - priority: 优先级
        """
        self.news_configs = news_configs
        # 快速失败策略：减少重试次数和延迟
        self.retry_handler = RetryHandler(max_retries=1, base_delay=0.5, max_delay=2.0)
        self.health_tracker = SourceHealthTracker()
        logger.info(f"✓ 新闻采集器初始化完成（配置 {len(news_configs)} 个新闻源）")
    
    def collect_all(self, days_back: int = 7) -> List[Dict]:
        """
        采集所有新闻源的最新内容
        
        Args:
            days_back: 采集最近N天的内容
            
        Returns:
            新闻条目列表
        """
        all_news = []
        cutoff_date = datetime.now() - timedelta(days=days_back)
        skipped_count = 0
        
        for config in self.news_configs:
            # 检查源是否健康
            if not self.health_tracker.is_healthy(config['name'], config['url']):
                skipped_count += 1
                logger.debug(f"⏭ 跳过不健康的新闻源: {config['name']}")
                continue
            
            try:
                news_items = self._collect_single_source(config, cutoff_date)
                all_news.extend(news_items)
                
                # 记录成功
                if news_items:
                    self.health_tracker.record_success(config['name'], config['url'])
                    logger.info(f"✓ {config['name']}: {len(news_items)} 条新闻")
                else:
                    logger.debug(f"⚠ {config['name']}: 无新条目")
                    
            except requests.exceptions.HTTPError as e:
                # HTTP 错误
                status_code = e.response.status_code if e.response else None
                error_msg = str(e)
                
                self.health_tracker.record_failure(
                    config['name'],
                    config['url'],
                    error_type='HTTPError',
                    error_message=error_msg,
                    status_code=status_code
                )
                
                if status_code == 404:
                    logger.warning(f"✗ {config['name']}: 404 Not Found (可能已失效)")
                else:
                    logger.error(f"✗ {config['name']}: HTTP {status_code} - {error_msg}")
                    
            except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as e:
                # 网络错误
                error_type = type(e).__name__
                error_msg = str(e)
                
                self.health_tracker.record_failure(
                    config['name'],
                    config['url'],
                    error_type=error_type,
                    error_message=error_msg
                )
                
                logger.error(f"✗ {config['name']}: 网络错误 ({error_type}) - {error_msg}")
                
            except Exception as e:
                # 其他错误
                error_msg = str(e)
                
                self.health_tracker.record_failure(
                    config['name'],
                    config['url'],
                    error_type=type(e).__name__,
                    error_message=error_msg
                )
                
                logger.error(f"✗ {config['name']} 采集失败: {error_msg}")
        
        # 记录统计信息
        health_summary = self.health_tracker.get_health_summary()
        logger.info(f"✓ 新闻采集完成: 总计 {len(all_news)} 条 (跳过 {skipped_count} 个不健康源)")
        if health_summary['unhealthy'] > 0:
            logger.warning(f"⚠ 有 {health_summary['unhealthy']} 个新闻源标记为不健康")
        
        return all_news
    
    def _collect_single_source(self, config: Dict, cutoff_date: datetime) -> List[Dict]:
        """
        采集单个新闻源
        
        Args:
            config: 新闻源配置
            cutoff_date: 截止日期
            
        Returns:
            新闻条目列表
        """
        news_items = []
        
        # 使用重试机制获取 RSS
        def fetch_feed():
            """获取 RSS feed（带重试，快速失败）"""
            session = self.retry_handler.create_session(timeout=8.0)
            response = session.get(config['url'], timeout=(5, 8))  # 连接5秒，读取8秒
            response.raise_for_status()
            return feedparser.parse(response.content)
        
        try:
            feed, error = self.retry_handler.retry_with_backoff(fetch_feed)
            
            if error:
                # 重试失败，抛出异常
                raise error
                
        except requests.exceptions.HTTPError:
            # HTTP 错误，重新抛出以便上层处理
            raise
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError):
            # 网络错误，重新抛出以便上层处理
            raise
        except Exception as e:
            logger.error(f"解析RSS失败 ({config['name']}): {str(e)}")
            raise  # 重新抛出以便上层记录失败
        
        for entry in feed.entries:
            # 解析发布时间
            published_date = self._parse_published_date(entry)
            
            # 过滤旧内容
            if published_date and published_date < cutoff_date:
                continue
            
            # 提取内容
            title = entry.get('title', 'No Title')
            link = entry.get('link', '')
            
            # 摘要处理（优先使用summary，否则使用description）
            summary = entry.get('summary', entry.get('description', ''))
            # 清理HTML标签（简单处理）
            if summary:
                summary = self._clean_html(summary)
            
            # 构建新闻条目
            news_item = {
                'title': title,
                'link': link,
                'source': config['name'],
                'published_date': published_date.strftime('%Y-%m-%d %H:%M:%S') if published_date else '',
                'summary': summary[:500] if summary else title,  # 限制摘要长度
                'category': config.get('category', 'industry_news'),
                'priority': config.get('priority', 8)
            }
            
            news_items.append(news_item)
        
        return news_items
    
    def _parse_published_date(self, entry) -> datetime:
        """
        解析发布时间
        
        Args:
            entry: RSS条目
            
        Returns:
            发布时间（datetime对象）
        """
        # 尝试多个字段
        for field in ['published_parsed', 'updated_parsed', 'created_parsed']:
            if hasattr(entry, field):
                time_struct = getattr(entry, field)
                if time_struct:
                    try:
                        return datetime(*time_struct[:6])
                    except:
                        pass
        
        # 如果都失败，返回当前时间
        return datetime.now()
    
    def _clean_html(self, text: str) -> str:
        """
        清理HTML标签
        
        Args:
            text: 原始文本
            
        Returns:
            清理后的文本
        """
        import re
        
        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)
        
        # 移除多余空白
        text = re.sub(r'\s+', ' ', text)
        
        # 解码HTML实体
        import html
        text = html.unescape(text)
        
        return text.strip()

