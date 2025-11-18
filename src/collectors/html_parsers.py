"""
HTML Parsers for RSS Collector
为不同网站结构提供自定义 HTML 解析器
"""

import logging
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from abc import ABC, abstractmethod
from bs4 import BeautifulSoup
import re
import requests
from urllib.parse import urljoin, urlsplit

logger = logging.getLogger(__name__)


class HTMLParser(ABC):
    """HTML 解析器基类"""
    
    @abstractmethod
    def parse(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """
        解析 HTML 页面，提取文章列表
        
        Args:
            soup: BeautifulSoup 对象
            base_url: 基础 URL，用于处理相对链接
            
        Returns:
            文章列表，每个文章包含 title, link, summary, published_date
        """
        pass
    
    def _normalize_url(self, url: str, base_url: str) -> str:
        """规范化 URL，处理相对链接"""
        if not url:
            return ""
        if url.startswith('http'):
            return url
        if url.startswith('/'):
            # 从 base_url 提取域名
            domain = '/'.join(base_url.split('/')[:3])
            return f"{domain}{url}"
        return f"{base_url.rstrip('/')}/{url.lstrip('/')}"
    
    def _extract_date(self, element, soup: BeautifulSoup) -> Optional[datetime]:
        """尝试从元素中提取日期"""
        # 尝试多种日期格式
        date_patterns = [
            r'(\d{4}-\d{2}-\d{2})',  # YYYY-MM-DD
            r'(\d{2}/\d{2}/\d{4})',  # MM/DD/YYYY
            r'(\d{1,2}\s+\w+\s+\d{4})',  # DD Month YYYY
        ]
        
        text = element.get_text() if hasattr(element, 'get_text') else str(element)
        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                try:
                    from dateutil import parser
                    return parser.parse(match.group(1))
                except:
                    pass
        
        return None


class GenericArticleParser(HTMLParser):
    """通用文章解析器（降级方案）"""
    
    def parse(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """尝试多种常见选择器"""
        articles = []
        
        # 尝试多种选择器策略
        selectors = [
            ('article', None),  # 标准 <article> 标签
            ('div[class*="article"]', None),  # class 包含 article 的 div
            ('div[class*="post"]', None),  # class 包含 post 的 div
            ('div[class*="entry"]', None),  # class 包含 entry 的 div
            ('li[class*="article"]', None),  # 列表项中的文章
            ('div[class*="card"]', None),  # 卡片式布局
        ]
        
        for selector, _ in selectors:
            try:
                elements = soup.select(selector)
                if elements:
                    logger.debug(f"使用选择器 '{selector}' 找到 {len(elements)} 个元素")
                    for elem in elements[:10]:  # 限制数量
                        article = self._extract_article(elem, base_url)
                        if article and article.get('title'):
                            articles.append(article)
                    
                    if articles:
                        break  # 找到文章就停止尝试其他选择器
            except Exception as e:
                logger.debug(f"选择器 '{selector}' 解析失败: {e}")
                continue
        
        return articles
    
    def _extract_article(self, element, base_url: str) -> Optional[Dict]:
        """从元素中提取文章信息"""
        try:
            # 尝试多种标题选择器
            title_elem = (
                element.find('h1') or
                element.find('h2') or
                element.find('h3') or
                element.find('h4') or
                element.find('a', class_=re.compile(r'title|heading', re.I))
            )
            
            if not title_elem:
                return None
            
            title = title_elem.get_text().strip()
            if not title:
                return None
            
            # 尝试多种链接选择器（注意：Python中三元表达式优先级高于“or”，因此需分开写）
            link_elem = element.find('a', href=True)
            if not link_elem and title_elem and title_elem.name != 'a':
                link_elem = title_elem.find('a', href=True)
            
            link = ""
            if link_elem:
                link = link_elem.get('href', '')
            elif title_elem and title_elem.name == 'a':
                link = title_elem.get('href', '')
            
            link = self._normalize_url(link, base_url)
            
            # 提取摘要
            summary_elem = (
                element.find('p') or
                element.find('div', class_=re.compile(r'summary|excerpt|description', re.I)) or
                element.find('span', class_=re.compile(r'summary|excerpt', re.I))
            )
            summary = summary_elem.get_text().strip()[:500] if summary_elem else ""
            
            # 尝试提取日期
            date_elem = (
                element.find('time') or
                element.find('span', class_=re.compile(r'date|time|published', re.I)) or
                element.find('div', class_=re.compile(r'date|time', re.I))
            )
            published_date = self._extract_date(date_elem, element) if date_elem else None
            
            return {
                'title': title,
                'link': link,
                'summary': summary,
                'published_date': published_date,
            }
        except Exception as e:
            logger.debug(f"提取文章信息失败: {e}")
            return None


class AnthropicBlogParser(HTMLParser):
    """Anthropic 博客专用解析器"""
    
    def parse(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """解析 Anthropic 博客页面"""
        articles = []
        
        # Anthropic 博客的特定结构
        # 尝试多种可能的选择器
        selectors = [
            'article',
            'div[class*="post"]',
            'div[class*="article"]',
            'li[class*="post"]',
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                logger.debug(f"Anthropic: 使用选择器 '{selector}' 找到 {len(elements)} 个元素")
                for elem in elements[:10]:
                    article = self._extract_article(elem, base_url)
                    if article and article.get('title'):
                        articles.append(article)
                if articles:
                    break
        
        return articles
    
    def _extract_article(self, element, base_url: str) -> Optional[Dict]:
        """提取 Anthropic 文章信息"""
        try:
            title_elem = element.find('h2') or element.find('h3') or element.find('h1')
            if not title_elem:
                return None
            
            title = title_elem.get_text().strip()
            link_elem = element.find('a', href=True) or (title_elem if title_elem.name == 'a' else None)
            
            link = ""
            if link_elem:
                link = link_elem.get('href', '')
            link = self._normalize_url(link, "https://www.anthropic.com")
            
            summary_elem = element.find('p')
            summary = summary_elem.get_text().strip()[:500] if summary_elem else ""
            
            return {
                'title': title,
                'link': link,
                'summary': summary,
                'published_date': None,  # Anthropic 博客通常不显示日期
            }
        except Exception as e:
            logger.debug(f"提取 Anthropic 文章失败: {e}")
            return None


class MistralBlogParser(HTMLParser):
    """Mistral AI 博客专用解析器"""
    
    def parse(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """解析 Mistral AI 博客页面"""
        articles = []
        
        # Mistral 可能使用特定的类名或结构
        elements = soup.select('article, div[class*="post"], div[class*="news-item"]')
        
        for elem in elements[:10]:
            article = self._extract_article(elem, base_url)
            if article and article.get('title'):
                articles.append(article)
        
        return articles
    
    def _extract_article(self, element, base_url: str) -> Optional[Dict]:
        """提取 Mistral 文章信息"""
        try:
            title_elem = element.find('h2') or element.find('h3') or element.find('a', class_=re.compile(r'title', re.I))
            if not title_elem:
                return None
            
            title = title_elem.get_text().strip()
            link_elem = element.find('a', href=True) or (title_elem if title_elem.name == 'a' else None)
            
            link = ""
            if link_elem:
                link = link_elem.get('href', '')
            link = self._normalize_url(link, base_url)
            
            summary_elem = element.find('p') or element.find('div', class_=re.compile(r'summary', re.I))
            summary = summary_elem.get_text().strip()[:500] if summary_elem else ""
            
            return {
                'title': title,
                'link': link,
                'summary': summary,
                'published_date': None,
            }
        except Exception as e:
            logger.debug(f"提取 Mistral 文章失败: {e}")
            return None


class HuggingFacePapersParser(HTMLParser):
    """Hugging Face Papers 专用解析器"""
    
    def parse(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """解析 Hugging Face Papers 页面"""
        articles = []
        
        # Hugging Face Papers 使用 <article> 标签
        elements = soup.select('article')
        
        for elem in elements[:20]:  # 最多取20篇论文
            article = self._extract_paper(elem, base_url)
            if article and article.get('title'):
                articles.append(article)
        
        return articles
    
    def _extract_paper(self, element, base_url: str) -> Optional[Dict]:
        """提取论文信息"""
        try:
            # 标题在 h3 标签中，包含链接
            title_elem = element.find('h3')
            if not title_elem:
                return None
            
            # 标题链接
            title_link = title_elem.find('a', href=True)
            if not title_link:
                return None
            
            title = title_link.get_text().strip()
            link = title_link.get('href', '')
            link = self._normalize_url(link, base_url)
            
            # 尝试提取作者/机构信息作为摘要
            author_elem = element.find('a', href=re.compile(r'/papers/|/[^/]+$'))
            summary = ""
            if author_elem:
                # 获取作者/机构名称
                author_text = author_elem.get_text().strip()
                # 尝试获取点赞数等信息
                likes_elem = element.find('a', href=re.compile(r'login.*papers'))
                if likes_elem:
                    likes_text = likes_elem.get_text().strip()
                    summary = f"Author/Org: {author_text}. Likes: {likes_text}"
                else:
                    summary = f"Author/Org: {author_text}"
            
            # 尝试从 URL 中提取日期（如果 URL 包含日期）
            published_date = None
            if '/date/' in base_url:
                date_match = re.search(r'/date/(\d{4}-\d{2}-\d{2})', base_url)
                if date_match:
                    try:
                        from dateutil import parser
                        published_date = parser.parse(date_match.group(1))
                    except:
                        pass
            
            return {
                'title': title,
                'link': link,
                'summary': summary,
                'published_date': published_date,
            }
        except Exception as e:
            logger.debug(f"提取 Hugging Face Paper 失败: {e}")
            return None


class HuggingFaceForumParser(HTMLParser):
    """Hugging Face 论坛专用解析器"""
    
    def parse(self, soup: BeautifulSoup, base_url: str) -> List[Dict]:
        """解析 Hugging Face 论坛页面"""
        articles = []
        
        # Discourse 论坛通常使用特定的类名
        # 尝试多种可能的选择器
        selectors = [
            'tr.topic-list-item',
            'div.topic-list-item',
            'article.topic',
            'div[class*="topic"]',
        ]
        
        for selector in selectors:
            elements = soup.select(selector)
            if elements:
                logger.debug(f"Hugging Face Forum: 使用选择器 '{selector}' 找到 {len(elements)} 个元素")
                for elem in elements[:20]:  # 最多取20个讨论
                    article = self._extract_topic(elem, base_url)
                    if article and article.get('title'):
                        articles.append(article)
                if articles:
                    break
        
        if not articles:
            articles = self._fetch_topics_from_api(base_url)
        
        return articles
    
    def _extract_topic(self, element, base_url: str) -> Optional[Dict]:
        """提取论坛讨论主题信息"""
        try:
            # 标题通常在链接中
            title_link = element.find('a', class_=re.compile(r'title|raw', re.I))
            if not title_link:
                # 尝试其他可能的标题选择器
                title_link = element.find('a', href=re.compile(r'/t/'))
            
            if not title_link:
                return None
            
            title = title_link.get_text().strip()
            if not title:
                return None
            
            link = title_link.get('href', '')
            link = self._normalize_url(link, base_url)
            
            # 尝试提取摘要（通常是第一段或描述）
            summary_elem = (
                element.find('div', class_=re.compile(r'excerpt|summary|description', re.I)) or
                element.find('p', class_=re.compile(r'excerpt', re.I)) or
                element.find('span', class_=re.compile(r'excerpt', re.I))
            )
            summary = summary_elem.get_text().strip()[:500] if summary_elem else ""
            
            # 尝试提取日期
            date_elem = (
                element.find('time') or
                element.find('span', class_=re.compile(r'relative-time|date', re.I))
            )
            published_date = self._extract_date(date_elem, element) if date_elem else None
            
            return {
                'title': title,
                'link': link,
                'summary': summary,
                'published_date': published_date,
            }
        except Exception as e:
            logger.debug(f"提取 Hugging Face Forum 主题失败: {e}")
            return None
    
    def _fetch_topics_from_api(self, base_url: str) -> List[Dict]:
        """当 HTML 结构变化时，回退到 Discourse JSON API。"""
        split = urlsplit(base_url)
        base_host = f"{split.scheme}://{split.netloc}"
        api_url = urljoin(base_host, '/latest.json')
        articles: List[Dict] = []
        try:
            response = requests.get(api_url, timeout=8)
            response.raise_for_status()
            data = response.json()
            topics = (data.get('topic_list') or {}).get('topics', [])
            users = {user['id']: user for user in (data.get('users') or [])}
            
            for topic in topics[:20]:
                title = topic.get('title')
                slug = topic.get('slug')
                topic_id = topic.get('id')
                if not (title and slug and topic_id):
                    continue
                link = f"{base_host}/t/{slug}/{topic_id}"
                summary = (topic.get('excerpt') or '').strip()
                
                published_date = None
                created_at = topic.get('created_at')
                if created_at:
                    try:
                        from dateutil import parser
                        published_date = parser.parse(created_at)
                    except Exception:
                        published_date = None
                
                articles.append({
                    'title': title,
                    'link': link,
                    'summary': summary,
                    'published_date': published_date,
                })
        except Exception as e:
            logger.debug(f"Hugging Face Forum JSON API 解析失败: {e}")
        return articles


class ParserRegistry:
    """解析器注册表"""
    
    def __init__(self):
        self._parsers: Dict[str, HTMLParser] = {}
        self._default_parser = GenericArticleParser()
        self._register_default_parsers()
    
    def _register_default_parsers(self):
        """注册默认解析器"""
        self.register('anthropic', AnthropicBlogParser())
        self.register('mistral', MistralBlogParser())
        self.register('huggingface', HuggingFacePapersParser())
        self.register('hugging face', HuggingFacePapersParser())
        self.register('huggingface forum', HuggingFaceForumParser())
        self.register('discuss.huggingface', HuggingFaceForumParser())
        self.register('generic', GenericArticleParser())
    
    def register(self, name: str, parser: HTMLParser):
        """注册解析器"""
        self._parsers[name.lower()] = parser
        logger.debug(f"注册 HTML 解析器: {name}")
    
    def get_parser(self, source_name: str, source_url: str) -> HTMLParser:
        """
        根据源名称和 URL 获取合适的解析器
        
        Args:
            source_name: 源名称
            source_url: 源 URL
            
        Returns:
            HTMLParser 实例
        """
        # 根据源名称匹配
        source_lower = source_name.lower()
        for key, parser in self._parsers.items():
            if key in source_lower:
                logger.debug(f"为 {source_name} 使用解析器: {key}")
                return parser
        
        # 根据 URL 匹配
        url_lower = source_url.lower()
        for key, parser in self._parsers.items():
            if key in url_lower:
                logger.debug(f"根据 URL 为 {source_name} 使用解析器: {key}")
                return parser
        
        # 默认使用通用解析器
        logger.debug(f"为 {source_name} 使用默认通用解析器")
        return self._default_parser


# 全局解析器注册表实例
_parser_registry = ParserRegistry()


def get_html_parser(source_name: str, source_url: str) -> HTMLParser:
    """
    获取 HTML 解析器的便捷函数
    
    Args:
        source_name: 源名称
        source_url: 源 URL
        
    Returns:
        HTMLParser 实例
    """
    return _parser_registry.get_parser(source_name, source_url)

