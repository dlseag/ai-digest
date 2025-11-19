"""
ProductHunt Collector
ProductHunt采集器：采集热门AI工具和产品
"""

import requests
from datetime import datetime, timedelta
import logging
from typing import List, Dict, Optional
import os

from src.utils.dedupe import normalize_url, unique_items

logger = logging.getLogger(__name__)


class ProductHuntCollector:
    """ProductHunt采集器"""
    
    def __init__(self, config: Dict):
        """
        初始化ProductHunt采集器
        
        Args:
            config: 配置字典，包含:
                - enabled: 是否启用
                - min_upvotes: 最小点赞数
                - topics: 主题列表（如 ["artificial-intelligence", "developer-tools"]）
                - priority: 优先级
        """
        self.enabled = config.get('enabled', True)
        self.min_upvotes = config.get('min_upvotes', 200)
        self.topics = config.get('topics', ['artificial-intelligence'])
        self.priority = config.get('priority', 8)
        
        # ProductHunt API Token（可选，无token有较低的rate limit）
        self.api_token = os.getenv('PRODUCTHUNT_API_TOKEN', '')
        
        # GraphQL API endpoint
        self.api_url = "https://api.producthunt.com/v2/api/graphql"
        
        if self.enabled:
            logger.info(f"✓ ProductHunt采集器初始化完成（最低点赞: {self.min_upvotes}）")
        else:
            logger.info("⚠ ProductHunt采集器已禁用")
    
    def collect(self, days_back: int = 7) -> List[Dict]:
        """
        采集ProductHunt热门AI工具
        
        Args:
            days_back: 采集最近N天的产品
            
        Returns:
            产品列表
        """
        if not self.enabled:
            logger.info("ProductHunt采集器已禁用，跳过")
            return []
        
        all_products = []
        
        # 如果没有API token，使用RSS作为fallback
        if not self.api_token:
            logger.warning("⚠ 未配置PRODUCTHUNT_API_TOKEN，使用RSS模式（功能受限）")
            return self._collect_from_rss(days_back)
        
        # 使用GraphQL API采集
        try:
            products = self._collect_from_api(days_back)
            all_products.extend(products)
            logger.info(f"✓ ProductHunt采集完成: {len(all_products)} 条产品")
        except Exception as e:
            logger.error(f"✗ ProductHunt采集失败: {str(e)}")
            logger.info("尝试使用RSS fallback...")
            all_products = self._collect_from_rss(days_back)
        
        return unique_items(
            all_products,
            lambda p: normalize_url(p.get('link', '')) or normalize_url(p.get('title', '')),
        )
    
    def _collect_from_api(self, days_back: int) -> List[Dict]:
        """
        通过GraphQL API采集（需要token）
        
        Args:
            days_back: 采集天数
            
        Returns:
            产品列表
        """
        products = []
        
        # 计算日期范围
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        # GraphQL查询
        query = """
        query ($postedAfter: DateTime!) {
          posts(order: VOTES, postedAfter: $postedAfter, first: 50) {
            edges {
              node {
                id
                name
                tagline
                description
                url
                votesCount
                createdAt
                topics {
                  edges {
                    node {
                      name
                    }
                  }
                }
              }
            }
          }
        }
        """
        
        variables = {
            "postedAfter": start_date.isoformat()
        }
        
        headers = {
            "Authorization": f"Bearer {self.api_token}",
            "Content-Type": "application/json"
        }
        
        try:
            response = requests.post(
                self.api_url,
                json={"query": query, "variables": variables},
                headers=headers,
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            
            # 解析结果
            edges = data.get('data', {}).get('posts', {}).get('edges', [])
            
            for edge in edges:
                node = edge.get('node', {})
                
                # 检查点赞数
                votes = node.get('votesCount', 0)
                if votes < self.min_upvotes:
                    continue
                
                # 检查主题
                topics = [t['node']['name'].lower() for t in node.get('topics', {}).get('edges', [])]
                if not any(topic in topics for topic in self.topics):
                    continue
                
                # 构建产品条目
                product = {
                    'title': node.get('name', ''),
                    'link': node.get('url', ''),
                    'source': f"ProductHunt ({votes} upvotes)",
                    'published_date': self._parse_datetime(node.get('createdAt', '')),
                    'summary': node.get('description') or node.get('tagline', ''),
                    'category': 'project',
                    'priority': self.priority
                }
                
                products.append(product)
        
        except Exception as e:
            logger.error(f"GraphQL API调用失败: {str(e)}")
            raise
        
        return unique_items(
            products,
            lambda p: normalize_url(p.get('link', '')) or normalize_url(p.get('title', '')),
        )
    
    def _collect_from_rss(self, days_back: int) -> List[Dict]:
        """
        从RSS采集（fallback，无需token但功能受限）
        
        Args:
            days_back: 采集天数
            
        Returns:
            产品列表
        """
        import feedparser
        
        products = []
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        # ProductHunt RSS（按主题）
        rss_urls = [
            "https://www.producthunt.com/feed/ai.rss",  # AI主题
            "https://www.producthunt.com/feed/developer-tools.rss"  # 开发者工具
        ]
        
        for rss_url in rss_urls:
            try:
                feed = feedparser.parse(rss_url)
                
                for entry in feed.entries[:10]:  # 限制每个源10条
                    # 解析发布时间
                    published_date = None
                    if hasattr(entry, 'published_parsed') and entry.published_parsed:
                        published_date = datetime(*entry.published_parsed[:6])
                    
                    # 过滤旧内容
                    if published_date and published_date < cutoff_date:
                        continue
                    
                    # 构建产品条目
                    product = {
                        'title': entry.get('title', ''),
                        'link': entry.get('link', ''),
                        'source': "ProductHunt",
                        'published_date': published_date.strftime('%Y-%m-%d %H:%M:%S') if published_date else '',
                        'summary': entry.get('summary', ''),
                        'category': 'project',
                        'priority': self.priority
                    }
                    
                    products.append(product)
                    
            except Exception as e:
                logger.error(f"RSS采集失败 ({rss_url}): {str(e)}")
        
        return unique_items(
            products,
            lambda p: normalize_url(p.get('link', '')) or normalize_url(p.get('title', '')),
        )
    
    def _parse_datetime(self, date_str: str) -> str:
        """
        解析ISO格式日期时间
        
        Args:
            date_str: ISO格式日期字符串
            
        Returns:
            格式化的日期字符串
        """
        try:
            dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
            return dt.strftime('%Y-%m-%d %H:%M:%S')
        except:
            return datetime.now().strftime('%Y-%m-%d %H:%M:%S')

