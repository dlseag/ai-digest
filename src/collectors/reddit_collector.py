"""
Reddit Collector
采集Reddit subreddit的热门帖子
"""

import logging
import os
from datetime import datetime, timedelta
from typing import List, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RedditItem:
    """Reddit帖子数据类"""
    title: str
    link: str
    summary: str
    published: datetime
    source: str
    category: str
    priority: int
    upvotes: int
    comments: int


class RedditCollector:
    """Reddit采集器"""
    
    def __init__(self, subreddit_configs: List[dict]):
        """
        初始化Reddit采集器
        
        Args:
            subreddit_configs: subreddit配置列表
        """
        self.configs = subreddit_configs
        self.reddit = None
        self._init_reddit_client()
    
    def _init_reddit_client(self):
        """初始化Reddit客户端"""
        try:
            import praw
            
            # 尝试从环境变量获取Reddit凭证
            client_id = os.getenv('REDDIT_CLIENT_ID')
            client_secret = os.getenv('REDDIT_CLIENT_SECRET')
            user_agent = os.getenv('REDDIT_USER_AGENT', 'AI Weekly Report Generator 1.0')
            
            if client_id and client_secret:
                self.reddit = praw.Reddit(
                    client_id=client_id,
                    client_secret=client_secret,
                    user_agent=user_agent
                )
                logger.info("✓ Reddit客户端初始化成功（使用凭证）")
            else:
                # 无凭证模式（只读）
                self.reddit = praw.Reddit(
                    client_id='dummy',
                    client_secret='dummy',
                    user_agent=user_agent,
                    check_for_async=False
                )
                logger.warning("⚠ Reddit客户端使用无凭证模式（功能受限）")
                
        except ImportError:
            logger.error("未安装praw库，跳过Reddit采集")
        except Exception as e:
            logger.error(f"Reddit客户端初始化失败: {str(e)}")
    
    def collect_all(self, days_back: int = 7) -> List[RedditItem]:
        """
        采集所有配置的subreddit
        
        Args:
            days_back: 采集最近N天的内容
            
        Returns:
            Reddit帖子列表
        """
        if not self.reddit:
            logger.warning("Reddit客户端未初始化，跳过采集")
            return []
        
        all_items = []
        cutoff_date = datetime.now() - timedelta(days=days_back)
        
        for config in self.configs:
            try:
                items = self._collect_subreddit(config, cutoff_date)
                all_items.extend(items)
                logger.info(f"✓ 采集 {config['name']}: {len(items)} 条目")
            except Exception as e:
                logger.error(f"采集{config['name']}失败: {str(e)}")
        
        logger.info(f"总共采集 {len(all_items)} 条Reddit帖子")
        return all_items
    
    def _collect_subreddit(self, config: dict, cutoff_date: datetime) -> List[RedditItem]:
        """
        采集单个subreddit
        
        Args:
            config: subreddit配置
            cutoff_date: 截止日期
            
        Returns:
            帖子列表
        """
        items = []
        
        try:
            subreddit = self.reddit.subreddit(config['subreddit'])
            limit = config.get('limit', 10)
            
            # 获取热门帖子
            for submission in subreddit.hot(limit=limit * 2):  # 多获取一些，过滤后可能不够
                # 解析时间
                created = datetime.fromtimestamp(submission.created_utc)
                
                # 过滤旧帖子
                if created < cutoff_date:
                    continue
                
                # 过滤置顶帖（通常是规则说明）
                if submission.stickied:
                    continue
                
                # 创建摘要
                summary = self._create_summary(submission)
                
                item = RedditItem(
                    title=submission.title,
                    link=f"https://reddit.com{submission.permalink}",
                    summary=summary,
                    published=created,
                    source=config['name'],
                    category=config['category'],
                    priority=config['priority'],
                    upvotes=submission.score,
                    comments=submission.num_comments
                )
                items.append(item)
                
                # 达到限制数量就停止
                if len(items) >= limit:
                    break
                    
        except Exception as e:
            logger.error(f"获取subreddit {config['subreddit']} 失败: {str(e)}")
        
        return items
    
    def _create_summary(self, submission) -> str:
        """
        创建帖子摘要
        
        Args:
            submission: Reddit submission对象
            
        Returns:
            摘要文本
        """
        # 优先使用selftext（自发帖文本）
        if submission.selftext:
            text = submission.selftext
            # 限制长度
            if len(text) > 400:
                text = text[:400] + "..."
        else:
            # 如果是链接帖，使用元数据
            text = f"讨论热度：{submission.score}分，{submission.num_comments}条评论"
            if submission.url:
                text += f"\n链接：{submission.url}"
        
        return text

