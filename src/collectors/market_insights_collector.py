"""
Market Insights Collector
市场洞察采集器：采集a16z、CB Insights等市场分析内容
"""

import logging
import requests
import feedparser
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass

from src.utils.dedupe import normalize_url, unique_items

logger = logging.getLogger(__name__)


@dataclass
class MarketInsight:
    """市场洞察数据类"""
    title: str
    source: str
    url: str
    published_date: str
    summary: str
    category: str  # 'funding', 'trend', 'analysis', 'report'
    
    def to_dict(self):
        """转换为字典"""
        return {
            'title': self.title,
            'source': self.source,
            'url': self.url,
            'published_date': self.published_date,
            'summary': self.summary,
            'category': self.category
        }


class MarketInsightsCollector:
    """市场洞察采集器"""
    
    def __init__(self, sources: List[Dict] = None):
        """
        初始化市场洞察采集器
        
        Args:
            sources: 数据源配置列表
        """
        # 默认数据源
        if sources is None:
            sources = [
                {
                    'name': 'a16z AI',
                    'url': 'https://a16z.com/tag/artificial-intelligence/feed/',
                    'category': 'analysis'
                },
                {
                    'name': 'Sequoia AI',
                    'url': 'https://www.sequoiacap.com/feed/',
                    'category': 'analysis'
                },
                {
                    'name': 'AI Index (Stanford)',
                    'url': 'https://aiindex.stanford.edu/feed/',
                    'category': 'report'
                }
            ]
        
        self.sources = sources
        logger.info(f"✓ 市场洞察采集器初始化完成（配置 {len(sources)} 个数据源）")
    
    def collect(self, days_back: int = 30) -> List[MarketInsight]:
        """
        采集市场洞察
        
        Args:
            days_back: 采集最近N天的内容（市场分析通常更新较慢，默认30天）
            
        Returns:
            市场洞察列表
        """
        try:
            logger.info(f"📈 开始采集市场洞察（最近 {days_back} 天）...")
            
            all_insights = []
            cutoff_date = datetime.now() - timedelta(days=days_back)
            
            for source in self.sources:
                insights = self._collect_single_source(source, cutoff_date)
                all_insights.extend(insights)
            
            # 去重（基于规范化URL，必要时回退到标题）
            unique_insights = unique_items(
                all_insights,
                lambda insight: normalize_url(insight.url) or normalize_url(insight.title),
            )
            
            logger.info(f"✓ 市场洞察采集完成: 总计 {len(unique_insights)} 条")
            
            # 按发布时间倒序排列
            unique_insights.sort(key=lambda x: x.published_date, reverse=True)
            
            return unique_insights
            
        except Exception as e:
            logger.error(f"采集市场洞察失败: {str(e)}")
            return []
    
    def _collect_single_source(self, source: Dict, cutoff_date: datetime) -> List[MarketInsight]:
        """
        从单个数据源采集
        
        Args:
            source: 数据源配置
            cutoff_date: 截止日期
            
        Returns:
            市场洞察列表
        """
        try:
            # 使用requests获取RSS内容（绕过SSL证书问题）
            response = requests.get(
                source['url'],
                timeout=10,
                headers={'User-Agent': 'Mozilla/5.0'}
            )
            response.raise_for_status()
            
            # 解析RSS
            feed = feedparser.parse(response.content)
            
            insights = []
            for entry in feed.entries[:10]:  # 每个源最多取10条
                try:
                    # 解析发布时间
                    published_date = self._parse_date(entry)
                    
                    # 检查是否在时间范围内
                    if published_date and published_date < cutoff_date:
                        continue
                    
                    # 提取摘要
                    summary = self._extract_summary(entry)
                    
                    # 创建MarketInsight对象
                    insight = MarketInsight(
                        title=entry.get('title', 'Untitled'),
                        source=source['name'],
                        url=entry.get('link', ''),
                        published_date=published_date.strftime('%Y-%m-%d') if published_date else '',
                        summary=summary,
                        category=source.get('category', 'analysis')
                    )
                    
                    insights.append(insight)
                    
                except Exception as e:
                    logger.debug(f"解析条目失败 ({source['name']}): {str(e)}")
                    continue
            
            logger.info(f"✓ {source['name']}: {len(insights)} 条洞察")
            return insights
            
        except requests.exceptions.RequestException as e:
            logger.error(f"获取RSS失败 ({source['name']}): {str(e)}")
            return []
        except Exception as e:
            logger.error(f"解析RSS失败 ({source['name']}): {str(e)}")
            return []
    
    def _parse_date(self, entry) -> Optional[datetime]:
        """解析RSS条目的发布时间"""
        try:
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                from time import mktime
                return datetime.fromtimestamp(mktime(entry.published_parsed))
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                from time import mktime
                return datetime.fromtimestamp(mktime(entry.updated_parsed))
            else:
                # 如果没有时间信息，使用当前时间
                return datetime.now()
        except Exception as e:
            logger.debug(f"解析时间失败: {str(e)}")
            return datetime.now()
    
    def _extract_summary(self, entry) -> str:
        """提取RSS条目的摘要"""
        try:
            # 尝试多个字段
            if hasattr(entry, 'summary') and entry.summary:
                # 清理HTML标签
                import re
                text = re.sub(r'<[^>]+>', '', entry.summary)
                # 限制长度
                if len(text) > 300:
                    text = text[:297] + '...'
                return text
            elif hasattr(entry, 'description') and entry.description:
                import re
                text = re.sub(r'<[^>]+>', '', entry.description)
                if len(text) > 300:
                    text = text[:297] + '...'
                return text
            else:
                return '（无摘要）'
        except Exception as e:
            logger.debug(f"提取摘要失败: {str(e)}")
            return '（无摘要）'
    
    def get_top_insights(self, all_insights: List[MarketInsight], top_n: int = 3) -> List[MarketInsight]:
        """
        获取Top N市场洞察
        
        Args:
            all_insights: 所有市场洞察
            top_n: 返回前N条
            
        Returns:
            Top N市场洞察
        """
        # 优先级排序：
        # 1. 最近发布的
        # 2. 来自知名机构的（a16z, Sequoia）
        
        prioritized = []
        for insight in all_insights:
            priority_score = 0
            
            # 来源加分
            if 'a16z' in insight.source.lower():
                priority_score += 10
            elif 'sequoia' in insight.source.lower():
                priority_score += 9
            elif 'stanford' in insight.source.lower():
                priority_score += 8
            
            # 类别加分
            if insight.category == 'report':
                priority_score += 5
            elif insight.category == 'analysis':
                priority_score += 3
            
            # 新鲜度加分（最近7天的内容）
            try:
                pub_date = datetime.strptime(insight.published_date, '%Y-%m-%d')
                days_ago = (datetime.now() - pub_date).days
                if days_ago <= 7:
                    priority_score += 5
                elif days_ago <= 14:
                    priority_score += 3
                elif days_ago <= 30:
                    priority_score += 1
            except:
                pass
            
            prioritized.append((priority_score, insight))
        
        # 按优先级排序
        prioritized.sort(key=lambda x: x[0], reverse=True)
        
        return [insight for _, insight in prioritized[:top_n]]

