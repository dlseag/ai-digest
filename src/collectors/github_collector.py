"""
GitHub Release Collector
GitHub仓库Release监控器
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass
from github import Github, GithubException
import os

logger = logging.getLogger(__name__)


@dataclass
class GitHubRelease:
    """GitHub Release数据类"""
    title: str
    version: str
    link: str
    description: str
    published: datetime
    repo_name: str
    category: str
    priority: int
    is_prerelease: bool
    author: Optional[str] = None


class GitHubCollector:
    """GitHub Release采集器"""
    
    def __init__(self, repos_config: List[Dict], github_token: Optional[str] = None):
        """
        初始化GitHub采集器
        
        Args:
            repos_config: 仓库配置列表
            github_token: GitHub Personal Access Token（可选，但强烈推荐）
        """
        self.repos_config = repos_config
        
        # 初始化GitHub客户端
        token = github_token or os.getenv('GITHUB_TOKEN')
        if token:
            self.github = Github(token)
            logger.info("✓ 使用GitHub Token（提高API限制）")
        else:
            self.github = Github()
            logger.warning("⚠ 未提供GitHub Token，API限制为60次/小时")
        
        self.releases: List[GitHubRelease] = []
    
    def collect_all(self, days_back: int = 7, include_prereleases: bool = False) -> List[GitHubRelease]:
        """
        采集所有仓库的最新Releases
        
        Args:
            days_back: 采集最近N天的Release，默认7天
            include_prereleases: 是否包括预发布版本
            
        Returns:
            采集到的Release列表
        """
        cutoff_date = datetime.now() - timedelta(days=days_back)
        all_releases = []
        
        for repo_config in self.repos_config:
            try:
                releases = self._collect_repo(repo_config, cutoff_date, include_prereleases)
                all_releases.extend(releases)
                logger.info(f"✓ 采集 {repo_config['repo']}: {len(releases)} 个Release")
            except GithubException as e:
                logger.error(f"✗ GitHub API错误 {repo_config['repo']}: {str(e)}")
            except Exception as e:
                logger.error(f"✗ 采集失败 {repo_config['repo']}: {str(e)}")
        
        # 按发布时间倒序排序
        all_releases.sort(key=lambda x: x.published, reverse=True)
        
        self.releases = all_releases
        logger.info(f"总共采集 {len(all_releases)} 个GitHub Release")
        return all_releases
    
    def _collect_repo(
        self, 
        repo_config: Dict, 
        cutoff_date: datetime,
        include_prereleases: bool
    ) -> List[GitHubRelease]:
        """
        采集单个仓库的Releases
        
        Args:
            repo_config: 仓库配置
            cutoff_date: 截止日期
            include_prereleases: 是否包括预发布版本
            
        Returns:
            该仓库的Release列表
        """
        releases = []
        
        try:
            repo = self.github.get_repo(repo_config['repo'])
            
            # 获取最近的releases（最多10个）
            for release in repo.get_releases()[:10]:
                # 检查发布时间
                if release.published_at and release.published_at.replace(tzinfo=None) < cutoff_date:
                    continue
                
                # 过滤预发布版本
                if release.prerelease and not include_prereleases:
                    continue
                
                # 创建Release对象
                github_release = GitHubRelease(
                    title=release.title or release.tag_name,
                    version=release.tag_name,
                    link=release.html_url,
                    description=self._clean_description(release.body or ""),
                    published=release.published_at.replace(tzinfo=None) if release.published_at else datetime.now(),
                    repo_name=repo_config['name'],
                    category=repo_config['category'],
                    priority=repo_config['priority'],
                    is_prerelease=release.prerelease,
                    author=release.author.login if release.author else None
                )
                
                releases.append(github_release)
                
        except Exception as e:
            logger.error(f"解析仓库失败 {repo_config['repo']}: {str(e)}")
        
        return releases
    
    def _clean_description(self, description: str, max_length: int = 1000) -> str:
        """
        清理Release描述文本
        
        Args:
            description: 原始描述
            max_length: 最大长度
            
        Returns:
            清理后的描述
        """
        if not description:
            return ""
        
        # 移除过长的描述
        if len(description) > max_length:
            description = description[:max_length] + "..."
        
        # 移除多余的空行
        lines = [line.strip() for line in description.split('\n') if line.strip()]
        description = '\n'.join(lines)
        
        return description
    
    def get_major_releases(self) -> List[GitHubRelease]:
        """
        获取重大版本发布（非预发布，且优先级高）
        
        Returns:
            重大版本Release列表
        """
        major = [
            r for r in self.releases 
            if not r.is_prerelease and r.priority >= 9
        ]
        return sorted(major, key=lambda x: x.published, reverse=True)
    
    def get_by_category(self, category: str) -> List[GitHubRelease]:
        """
        按类别获取Releases
        
        Args:
            category: 类别名称（如：framework, sdk, inference）
            
        Returns:
            该类别的Release列表
        """
        return [r for r in self.releases if r.category == category]
    
    def get_breaking_changes(self) -> List[GitHubRelease]:
        """
        检测可能包含Breaking Changes的Release
        （基于版本号：主版本号变化或描述中包含关键词）
        
        Returns:
            可能包含Breaking Changes的Release列表
        """
        breaking = []
        keywords = ['breaking', 'breaking change', 'migration', 'deprecated', 'removed']
        
        for release in self.releases:
            # 检查描述中的关键词
            description_lower = release.description.lower()
            if any(keyword in description_lower for keyword in keywords):
                breaking.append(release)
                continue
            
            # 检查主版本号变化（如：v1.0.0 -> v2.0.0）
            version = release.version.lstrip('v')
            if '.' in version:
                major_version = version.split('.')[0]
                if major_version != '0' and version.endswith('.0.0'):
                    breaking.append(release)
        
        return breaking
    
    def check_rate_limit(self) -> Dict:
        """
        检查GitHub API剩余配额
        
        Returns:
            包含限制信息的字典
        """
        try:
            rate_limit = self.github.get_rate_limit()
            core = rate_limit.core
            
            return {
                'limit': core.limit,
                'remaining': core.remaining,
                'reset_time': core.reset.strftime('%Y-%m-%d %H:%M:%S')
            }
        except Exception as e:
            logger.error(f"获取rate limit失败: {str(e)}")
            return {}

