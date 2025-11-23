"""
Report Generator
报告生成器：使用Jinja2模板生成Markdown周报
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Set
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import os

from src.learning.weight_adjuster import WeightAdjuster
from src.learning.reranker import ContentReranker, ProjectActivityTracker
from src.memory.user_profile_manager import UserProfileManager
from src.utils.dedupe import make_dedupe_key, mark_unique

logger = logging.getLogger(__name__)


class ReportGenerator:
    """周报生成器"""
    
    def __init__(
        self,
        template_dir: Optional[str] = None,
        version: str = "0.1.0",
        headline_source_limit: int = 2,
    ):
        """
        初始化报告生成器
        
        Args:
            template_dir: 模板目录路径
            version: 系统版本号
        """
        # 默认模板目录
        if template_dir is None:
            project_root = Path(__file__).parent.parent.parent
            template_dir = str(project_root / "templates")
        else:
            project_root = Path(template_dir).parent
        
        self.template_dir = template_dir
        self.version = version
        self.headline_source_limit = max(1, headline_source_limit)
        self.project_root = project_root
        deep_dive_env = os.getenv("DEEP_DIVE_ENABLED", "false").strip().lower()
        self.deep_dive_enabled = deep_dive_env in ("1", "true", "yes", "on")
        
        # 初始化权重调整器
        try:
            self.weight_adjuster = WeightAdjuster()
            logger.info("✓ 权重调整器已加载")
        except Exception as e:
            logger.warning(f"⚠️  权重调整器初始化失败: {e}")
            self.weight_adjuster = None
        
        # 初始化用户画像管理器（用于重排）
        try:
            profile_path = self.project_root / "config" / "user_profile.yaml"
            if profile_path.exists():
                self.profile_manager = UserProfileManager(profile_path=profile_path)
                logger.info("✓ 用户画像管理器已加载")
            else:
                logger.info("ℹ️  用户画像文件不存在，跳过重排功能")
                self.profile_manager = None
        except Exception as e:
            logger.warning(f"⚠️  用户画像管理器初始化失败: {e}")
            self.profile_manager = None
        
        # 初始化重排器
        try:
            self.reranker = ContentReranker(
                profile_manager=self.profile_manager,
                weight_adjuster=self.weight_adjuster,
            )
            logger.info("✓ 内容重排器已加载")
        except Exception as e:
            logger.warning(f"⚠️  内容重排器初始化失败: {e}")
            self.reranker = None
        
        # 初始化Jinja2环境
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
        # 添加自定义过滤器
        import hashlib
        def md5_filter(text):
            return hashlib.md5(str(text).encode()).hexdigest()
        self.env.filters['md5'] = md5_filter
        
        logger.info(f"✓ 报告生成器初始化完成（模板目录：{template_dir}）")
    
    def generate_report(
        self,
        processed_items: List,
        action_items: Dict[str, List[str]],
        leaderboard_data: List[Dict] = None,
        leaderboard_update_time: str = '',
        market_insights: List[Dict] = None,
        output_path: Optional[str] = None,
        learning_results: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        生成周报
        
        Args:
            processed_items: AI处理后的条目列表
            action_items: 行动清单
            leaderboard_data: LMSYS排行榜数据
            leaderboard_update_time: 排行榜更新时间
            market_insights: 市场洞察数据
            output_path: 输出文件路径（可选）
            
        Returns:
            生成的Markdown文本
        """
        # 按类别分组
        categorized = self._categorize_items(processed_items)

        # 去重控制：优先级高的板块先占位
        used_keys: Set[str] = set()

        sorted_by_priority = sorted(
            processed_items,
            key=lambda x: getattr(x, 'personal_priority', getattr(x, 'relevance_score', 0)),
            reverse=True
        )

        must_read_items: List[Any] = []
        source_counts: Dict[str, int] = {}  # 追踪每个来源的数量
        max_per_source = 2  # 每个来源最多2条
        
        for item in sorted_by_priority:
            if getattr(item, 'personal_priority', 0) < 8:
                continue
            if getattr(item, 'is_release', False) and not getattr(item, 'promote_release', False):
                continue

            if not mark_unique(item, used_keys, self._make_dedupe_key):
                continue
            
            # 检查来源多样性
            source = getattr(item, 'source', '')
            source_key = self._normalize_source(source)
            
            # 限制arXiv论文数量（最多2条）
            if 'arxiv' in source_key.lower():
                if source_counts.get('arxiv', 0) >= max_per_source:
                    continue
            
            # 限制同一来源的数量
            if source_counts.get(source_key, 0) >= max_per_source:
                continue

            must_read_items.append(item)
            setattr(item, 'exploration_pick', False)
            source_counts[source_key] = source_counts.get(source_key, 0) + 1
            
            # 特殊处理：arXiv统一计数
            if 'arxiv' in source_key.lower():
                source_counts['arxiv'] = source_counts.get('arxiv', 0) + 1
            
            if len(must_read_items) >= 5:
                break
        
        # Phase 1.3: 应用相关性重排
        if self.reranker and must_read_items:
            try:
                logger.info(f"🔄 对 {len(must_read_items)} 条必看内容进行重排...")
                must_read_items = self.reranker.rerank_items(must_read_items)
                logger.info("✓ 重排完成")
            except Exception as e:
                logger.warning(f"⚠️  重排失败，使用原始顺序: {e}")

        # 头条需在必看之后筛选，避免重复
        top_headlines = self._select_top_headlines(processed_items, top_count=10, used_keys=used_keys)

        selected_titles = {item.title for item in top_headlines}
        selected_titles.update(item.title for item in must_read_items)

        appendix_items: List[Any] = []
        for item in sorted_by_priority:
            if item.title in selected_titles:
                continue
            priority = getattr(item, 'personal_priority', 0)
            if not (6 <= priority <= 8):
                continue
            if getattr(item, 'is_release', False) and not getattr(item, 'promote_release', False):
                continue

            if not mark_unique(item, used_keys, self._make_dedupe_key):
                continue
            
            appendix_items.append(item)
            if len(appendix_items) >= 15:
                break

        selected_titles.update(item.title for item in appendix_items)
        
        # 过滤action_items，排除已在必看内容和头条中出现的条目
        filtered_action_items = self._filter_action_items(action_items, must_read_items, top_headlines)
        
        # 准备模板数据
        paper_radar = self._build_paper_radar(processed_items, used_keys)

        framework_items: List[Any] = []
        for item in categorized.get('framework', []):
            if item.title in selected_titles:
                continue
            if not mark_unique(item, used_keys, self._make_dedupe_key):
                continue
            framework_items.append(item)
            if len(framework_items) >= 5:
                break

        model_items: List[Any] = []
        for item in categorized.get('model', []):
            if item.title in selected_titles:
                continue
            if not mark_unique(item, used_keys, self._make_dedupe_key):
                continue
            model_items.append(item)
            if len(model_items) >= 5:
                break

        article_items: List[Any] = []
        for item in categorized.get('article', []):
            if item.title in selected_titles:
                continue
            if not mark_unique(item, used_keys, self._make_dedupe_key):
                continue
            article_items.append(item)
            if len(article_items) >= 3:
                break

        project_items: List[Any] = []
        for item in categorized.get('project', []):
            if item.title in selected_titles:
                continue
            if not mark_unique(item, used_keys, self._make_dedupe_key):
                continue
            project_items.append(item)
            if len(project_items) >= 3:
                break
        
        template_data = {
            'report_date': datetime.now().strftime('%Y年%m月%d日'),
            'generation_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'version': self.version,
            'deep_dive_enabled': self.deep_dive_enabled,
            'top_headlines': top_headlines,
            'action_items': filtered_action_items,
            'must_read_items': must_read_items,
            'appendix_items': appendix_items,
            'leaderboard_data': leaderboard_data if leaderboard_data else [],
            'leaderboard_update_time': leaderboard_update_time,
            'market_insights': market_insights if market_insights else [],
            'framework_items': framework_items,
            'model_items': model_items,
            'article_items': article_items,
            'project_items': project_items,
            'stats': self._generate_stats(processed_items, categorized),
            'learning_results': learning_results or {},
            'paper_radar': paper_radar,
        }
        
        # 渲染模板
        template = self.env.get_template('report_template.md.jinja')
        report_markdown = template.render(**template_data)
        
        # 保存到文件
        if output_path:
            self._save_report(report_markdown, output_path)
        
        logger.info("✓ 周报生成完成")
        return report_markdown
    
    def generate_html_report(
        self,
        processed_items: List,
        action_items: Dict[str, List[str]],
        leaderboard_data: List[Dict] = None,
        leaderboard_update_time: str = '',
        market_insights: List[Dict] = None,
        output_path: Optional[str] = None,
        learning_results: Optional[Dict[str, Any]] = None,
        report_id: Optional[str] = None,
    ) -> str:
        """
        生成HTML版本的周报（带评分功能）
        
        Args:
            processed_items: AI处理后的条目列表
            action_items: 行动清单
            leaderboard_data: LMSYS排行榜数据
            leaderboard_update_time: 排行榜更新时间
            market_insights: 市场洞察数据
            output_path: 输出文件路径（可选）
            learning_results: 学习结果
            report_id: 报告ID（用于追踪）
            
        Returns:
            生成的HTML文本
        """
        import hashlib
        from datetime import datetime
        
        # 为每个item生成唯一ID并确保有url属性（确保所有item都有id和url属性）
        for item in processed_items:
            # 确保有 url 属性（从 link 转换）
            if not hasattr(item, 'url') or not getattr(item, 'url', None):
                link = getattr(item, 'link', '')
                if link:
                    setattr(item, 'url', link)
                else:
                    setattr(item, 'url', '')
            
            url = getattr(item, 'url', '')
            title = getattr(item, 'title', '')
            unique_str = f"{url}{title}"
            item_id = hashlib.md5(unique_str.encode()).hexdigest()[:12]
            # 动态添加id属性
            if not hasattr(item, 'id'):
                setattr(item, 'id', item_id)
            elif not getattr(item, 'id', None):
                setattr(item, 'id', item_id)
        
        # 简化版本：只保留头条和论文两个板块
        used_keys: Set[str] = set()
        
        # 选择头条（扩展至15-20条）
        top_headlines = self._select_top_headlines(processed_items, top_count=20, used_keys=used_keys)
        
        # 选择论文精选
        featured_papers = self._select_featured_papers(processed_items, top_count=10, used_keys=used_keys)
        
        # 选择 Fintech 相关内容（独立去重，不共享used_keys，允许与头条重复）
        fintech_items = self._select_fintech_items(processed_items, top_count=15, used_keys=set())
        
        # 准备模板数据
        report_date = datetime.now().strftime('%Y年%m月%d日')
        generation_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        # 过滤 action_items（如果提供）
        filtered_action_items = {}
        if action_items:
            filtered_action_items = self._filter_action_items(action_items, [], top_headlines)
        
        template_data = {
            'report_date': report_date,
            'generation_time': generation_time,
            'report_id': report_id or f"report_{datetime.now().strftime('%Y-%m-%d')}",
            'deep_dive_enabled': self.deep_dive_enabled,
            'top_headlines': top_headlines,
            'featured_papers': featured_papers,
            'fintech_items': fintech_items,
            'leaderboard_data': leaderboard_data or [],
            'leaderboard_update_time': leaderboard_update_time,
            'market_insights': market_insights or [],
            'learning_results': learning_results or {},
        }
        
        # 渲染HTML模板
        template = self.env.get_template('report_template.html.jinja')
        report_html = template.render(**template_data)
        
        # 保存到文件
        if output_path:
            html_path = str(output_path).replace('.md', '.html')
            self._save_report(report_html, html_path)
            logger.info(f"✓ HTML报告已保存到: {html_path}")
        
        return report_html
    
    def _apply_dynamic_weight(self, item: Any, base_score: float) -> float:
        """
        应用动态权重到基础分数
        
        Args:
            item: 内容项目
            base_score: 基础分数（relevance_score 或 headline_priority）
        
        Returns:
            加权后的分数
        """
        if not self.weight_adjuster:
            return base_score
        
        # 获取来源权重
        source = getattr(item, 'source', '')
        source_weight = self.weight_adjuster.get_weight('sources', source)
        
        # 获取类别权重
        category = getattr(item, 'category', '')
        type_weight = self.weight_adjuster.get_weight('content_types', category)
        
        # 组合权重：来源权重 * 类别权重
        combined_weight = source_weight * type_weight
        
        # 应用权重
        weighted_score = base_score * combined_weight
        
        logger.debug(
            f"权重应用: {source} ({source_weight:.2f}) × {category} ({type_weight:.2f}) "
            f"= {combined_weight:.2f} | {base_score:.1f} → {weighted_score:.1f}"
        )
        
        return weighted_score
    
    def _select_featured_papers(self, processed_items: List, top_count: int = 8, used_keys: Optional[Set[str]] = None) -> List:
        """
        选择论文精选，只保留Hugging Face Papers和Papers with Code
        
        策略：
        1. 只包含Hugging Face Papers和Papers with Code（排除arXiv直接来源）
        2. 来源优先级：Hugging Face Papers > Papers with Code
        3. 70% 相关性 + 30% 探索性（避免信息茧房）
        4. 去重，避免重复
        
        Args:
            processed_items: 处理后的条目列表
            top_count: 需要选择的论文数量
            used_keys: 已使用的去重键集合（会被更新）
            
        Returns:
            论文条目列表
        """
        if used_keys is None:
            used_keys = set()
        dedupe_pool = used_keys
        
        # 筛选论文类内容，只保留Hugging Face Papers和Papers with Code
        papers = [
            item for item in processed_items 
            if getattr(item, 'category', '') == 'paper'
            and self._make_dedupe_key(item) not in dedupe_pool
            and self._is_curated_paper_source(getattr(item, 'source', ''))
        ]
        
        # 定义来源优先级（数字越大优先级越高）
        def get_source_priority(source: str) -> int:
            source_lower = source.lower()
            if 'hugging face' in source_lower:
                return 2  # 最高优先级：社区筛选
            elif 'papers with code' in source_lower:
                return 1  # 次高优先级：带代码实现
            else:
                return 0
        
        # 应用动态权重排序，并考虑来源优先级
        for paper in papers:
            base_score = getattr(paper, 'personal_priority', getattr(paper, 'relevance_score', 0))
            weighted_score = self._apply_dynamic_weight(paper, base_score)
            
            # 来源优先级加成（Hugging Face +2分，Papers with Code +1分）
            source_priority = get_source_priority(getattr(paper, 'source', ''))
            if source_priority == 2:  # Hugging Face Papers
                weighted_score += 2.0
            elif source_priority == 1:  # Papers with Code
                weighted_score += 1.0
            
            setattr(paper, 'weighted_score', weighted_score)
            setattr(paper, 'source_priority', source_priority)
        
        # 策略：70% 高相关 + 30% 探索
        target_relevant = int(top_count * 0.7)  # 5-6篇高相关
        target_exploration = top_count - target_relevant  # 2-3篇探索性
        
        featured_papers = []
        seen_sources: Dict[str, int] = {}
        max_per_source = 3  # 每个来源最多3篇论文
        
        # 第一阶段：选择高相关论文（选项3: 降低阈值从 >= 7 到 >= 6）
        relevant_papers = [p for p in papers if getattr(p, 'personal_priority', 0) >= 6]
        relevant_papers.sort(key=lambda x: getattr(x, 'weighted_score', 0), reverse=True)
        
        for paper in relevant_papers:
            if len(featured_papers) >= target_relevant:
                break
            
            source_key = self._normalize_source(getattr(paper, 'source', ''))
            dedupe_key = self._make_dedupe_key(paper)
            
            if dedupe_key in dedupe_pool:
                continue
            
            # 限制同一来源的数量
            if seen_sources.get(source_key, 0) >= max_per_source:
                continue
            
            featured_papers.append(paper)
            dedupe_pool.add(dedupe_key)
            seen_sources[source_key] = seen_sources.get(source_key, 0) + 1
        
        # 第二阶段：添加探索性论文（热门但不一定高度相关）
        # 策略：优先 Hugging Face Papers > Papers with Code
        exploration_papers = [
            p for p in papers 
            if getattr(p, 'personal_priority', 0) < 6  # 不那么相关
            and self._make_dedupe_key(p) not in dedupe_pool
        ]
        
        # 按来源优先级和质量排序
        exploration_papers.sort(
            key=lambda x: (
                getattr(x, 'source_priority', 0),  # 来源优先级最重要
                getattr(x, 'relevance_score', 0),  # 其次是相关性
                getattr(x, 'weighted_score', 0)    # 最后是加权分数
            ),
            reverse=True
        )
        
        for paper in exploration_papers:
            if len(featured_papers) >= top_count:
                break
            
            source_key = self._normalize_source(getattr(paper, 'source', ''))
            dedupe_key = self._make_dedupe_key(paper)
            
            if dedupe_key in dedupe_pool:
                continue
            
            if seen_sources.get(source_key, 0) >= max_per_source:
                continue
            
            featured_papers.append(paper)
            dedupe_pool.add(dedupe_key)
            seen_sources[source_key] = seen_sources.get(source_key, 0) + 1
            
            logger.info(f"🔍 添加探索性论文: {paper.title} (priority={getattr(paper, 'personal_priority', 0)})")
        
        # 统计来源分布
        source_stats = {}
        for paper in featured_papers:
            source = getattr(paper, 'source', 'Unknown')
            source_stats[source] = source_stats.get(source, 0) + 1
        
        relevant_count = len([p for p in featured_papers if getattr(p, 'personal_priority', 0) >= 6])
        exploration_count = len(featured_papers) - relevant_count
        
        logger.info(f"✓ 选择了 {len(featured_papers)} 篇论文精选（{relevant_count} 相关 + {exploration_count} 探索）")
        logger.info(f"  来源分布: {', '.join([f'{k}: {v}' for k, v in sorted(source_stats.items(), key=lambda x: x[1], reverse=True)])}")
        
        return featured_papers
    
    def _select_fintech_items(self, processed_items: List, top_count: int = 10, used_keys: Optional[Set[str]] = None) -> List:
        """
        选择 Fintech 相关的内容
        
        Args:
            processed_items: 处理后的条目列表
            top_count: 需要选择的数量
            used_keys: 已使用的去重键集合（会被更新）
            
        Returns:
            Fintech 相关条目列表
        """
        if used_keys is None:
            used_keys = set()
        dedupe_pool = used_keys
        
        # Fintech 关键词列表（扩展匹配）
        fintech_keywords = [
            'Capital One', 'JPMorgan', 'Goldman', 'Morgan Stanley', 
            'American Express', 'PayPal', 'Stripe', 'Square', 
            'Fidelity', 'BlackRock', 'Vanguard', 'Fintech', 
            'Fintech Times', 'The Fintech Times', 'Finextra', 
            'TechCrunch Fintech', 'fintech', 'FinTech', 'FINtech',
            'financial technology', 'banking tech', 'payment tech',
            'asset management', 'wealth management', 'robo-advisor',
            'fraud detection', 'credit risk', 'compliance automation'
        ]
        
        # VC/Startup 关键词（扩展匹配）
        vc_keywords = [
            'Y Combinator', 'YC', 'a16z', 'Sequoia', 
            'Launch HN', 'Crunchbase', 'TechCrunch Fintech',
            'ycombinator', 'Y Combinator Blog'
        ]
        
        # Fintech 相关源名称（完整匹配）
        fintech_sources = [
            'Fintech News', 'The Fintech Times', 'Finextra',
            'TechCrunch Fintech', 'Crunchbase News - Fintech'
        ]
        
        # 筛选 Fintech 相关的内容
        fintech_items = []
        for item in processed_items:
            source = getattr(item, 'source', '')
            title = getattr(item, 'title', '')
            summary = getattr(item, 'summary', '') or getattr(item, 'ai_summary', '')
            
            # 检查源名称是否完全匹配
            is_fintech_source = any(fs in source for fs in fintech_sources)
            
            # 检查是否匹配 Fintech 或 VC 关键词（在源、标题或摘要中）
            is_fintech = is_fintech_source or any(
                kw.lower() in source.lower() or 
                kw.lower() in title.lower() or 
                kw.lower() in summary.lower() 
                for kw in fintech_keywords
            )
            is_vc = any(
                kw.lower() in source.lower() or 
                kw.lower() in title.lower() or 
                kw.lower() in summary.lower()
                for kw in vc_keywords
            )
            
            if (is_fintech or is_vc) and self._make_dedupe_key(item) not in dedupe_pool:
                fintech_items.append(item)
                dedupe_pool.add(self._make_dedupe_key(item))
        
        # 按优先级排序
        fintech_items.sort(
            key=lambda x: getattr(x, 'personal_priority', getattr(x, 'relevance_score', 0)),
            reverse=True
        )
        
        # 记录日志
        logger.info(f"✓ 选择了 {len(fintech_items)} 条 Fintech 相关内容（Top {top_count}）")
        if fintech_items:
            source_stats = {}
            for item in fintech_items[:top_count]:
                source = getattr(item, 'source', 'unknown')
                source_stats[source] = source_stats.get(source, 0) + 1
            logger.info(f"  来源分布: {', '.join([f'{k}: {v}' for k, v in sorted(source_stats.items(), key=lambda x: x[1], reverse=True)])}")
        
        # 返回 Top N
        return fintech_items[:top_count]
    
    def _select_top_headlines(self, processed_items: List, top_count: int = 10, used_keys: Optional[Set[str]] = None) -> List:
        """
        选择头条列表，来源：主流媒体、个人博客、官方博客、Hacker News
        
        策略：
        1. 优先级：主流媒体 > 官方博客 > Newsletter/个人博客 > Hacker News
        2. headline类别优先，按headline_priority排序
        3. 如果headline不足，补充高分article/project（排除论文）
        4. 来源多样性：每个来源最多3条（扩展至15-20条总量）
        
        Args:
            processed_items: 处理后的条目列表
            top_count: 需要选择的头条数量
            used_keys: 已使用的去重键集合（会被更新）
            
        Returns:
            头条条目列表
        """
        if used_keys is None:
            used_keys = set()
        dedupe_pool = used_keys
        
        # 每个来源最多3条（适应15-20条的总量）
        max_per_source = 3

        # 先收集所有 headline 类别的条目，并过滤论文来源
        all_headlines = [item for item in processed_items if item.category == 'headline']
        logger.debug(f"📊 发现 {len(all_headlines)} 条 headline 类别的条目")
        for item in all_headlines[:5]:  # 只显示前5条
            source = getattr(item, 'source', '')
            is_paper = self._is_curated_paper_source(source)
            logger.debug(f"  - {item.title[:50]}... | 来源: {source} | 是论文源: {is_paper}")
        
        headlines = [
            item for item in processed_items 
            if item.category == 'headline'
            and 'Towards Data Science' not in item.source
            and not self._is_curated_paper_source(getattr(item, 'source', ''))  # 排除论文来源
            and not (getattr(item, 'is_release', False) and not getattr(item, 'promote_release', False))
            and self._make_dedupe_key(item) not in dedupe_pool
        ]
        logger.info(f"✓ 过滤后剩余 {len(headlines)} 条 headline")
        headlines.sort(key=lambda x: getattr(x, 'headline_priority', 0), reverse=True)
        
        seen_sources: Dict[str, int] = {}
        unique_headlines = []
        
        for item in headlines:
            source_key = self._normalize_source(item.source)
            dedupe_key = self._make_dedupe_key(item)
            
            if dedupe_key in dedupe_pool:
                continue
            if seen_sources.get(source_key, 0) >= max_per_source:
                continue
            if getattr(item, 'is_release', False) and not getattr(item, 'promote_release', False):
                continue
                
            unique_headlines.append(item)
            dedupe_pool.add(dedupe_key)
            seen_sources[source_key] = seen_sources.get(source_key, 0) + 1
            
            if len(unique_headlines) >= top_count:
                break
        
        # 第二步：补充高质量article/project（包含GitHub Release，排除论文）
        if len(unique_headlines) < top_count:
            others = [
                item for item in processed_items 
                if item.category in ['article', 'project', 'framework']  # 包含framework以获取GitHub Release
                and getattr(item, 'category', '') != 'paper'  # 明确排除论文类别
                and not self._is_curated_paper_source(getattr(item, 'source', ''))  # 排除论文来源
                and getattr(item, 'relevance_score', 0) >= 6  # 降低阈值以获取更多内容
                and 'Towards Data Science' not in item.source
                and self._make_dedupe_key(item) not in dedupe_pool
            ]
            others.sort(key=lambda x: getattr(x, 'relevance_score', 0), reverse=True)
            
            for item in others:
                if len(unique_headlines) >= top_count:
                    break
                
                source_key = self._normalize_source(item.source)
                dedupe_key = self._make_dedupe_key(item)
                
                if dedupe_key in dedupe_pool:
                    continue
                if seen_sources.get(source_key, 0) >= max_per_source:
                    continue
                if getattr(item, 'is_release', False) and not getattr(item, 'promote_release', False):
                    continue
                    
                unique_headlines.append(item)
                dedupe_pool.add(dedupe_key)
                seen_sources[source_key] = seen_sources.get(source_key, 0) + 1
        
        # 第三步：如果仍不足，补充其他内容（排除model和paper）
        if len(unique_headlines) < top_count:
            remaining = [
                item for item in processed_items 
                if item not in unique_headlines
                and getattr(item, 'category', '') not in ['model', 'paper']  # 排除model和paper类别
                and not self._is_curated_paper_source(getattr(item, 'source', ''))  # 排除论文来源
                and 'Towards Data Science' not in getattr(item, 'source', '')
                and self._make_dedupe_key(item) not in dedupe_pool
            ]
            remaining.sort(key=lambda x: getattr(x, 'relevance_score', 0), reverse=True)
            
            for item in remaining:
                if len(unique_headlines) >= top_count:
                    break
                
                # 过滤纯版本号的 Release
                if getattr(item, 'is_release', False) and not getattr(item, 'promote_release', False):
                    continue
                
                source_key = self._normalize_source(getattr(item, 'source', ''))
                if seen_sources.get(source_key, 0) >= max_per_source:
                    logger.debug(f"⏭ 跳过来源 {source_key}：已达上限 ({max_per_source}条)")
                    continue
                
                dedupe_key = self._make_dedupe_key(item)
                if dedupe_key not in dedupe_pool:
                    unique_headlines.append(item)
                    dedupe_pool.add(dedupe_key)
                    seen_sources[source_key] = seen_sources.get(source_key, 0) + 1
        
        # 记录详细筛选信息
        category_dist = {}
        source_dist = {}
        for item in unique_headlines:
            category_dist[item.category] = category_dist.get(item.category, 0) + 1
            source_key = self._normalize_source(item.source)
            source_dist[source_key] = source_dist.get(source_key, 0) + 1
        
        logger.info(f"✓ Top {top_count}筛选完成: {len(unique_headlines)}条")
        logger.info(f"  分类分布: {category_dist}")
        logger.info(f"  来源分布: {source_dist}")
        
        # 警告：如果arXiv占比过高
        arxiv_count = source_dist.get('arxiv', 0)
        if arxiv_count > len(unique_headlines) * 0.4:  # 超过40%
            logger.warning(f"⚠️  arXiv论文占比过高: {arxiv_count}/{len(unique_headlines)} = {arxiv_count/len(unique_headlines)*100:.1f}%")
        
        return unique_headlines[:top_count]
    
    def _categorize_items(self, items: List) -> Dict[str, List]:
        """
        按类别分组条目
        
        Args:
            items: 处理后的条目列表
            
        Returns:
            分类后的字典
        """
        categorized = {
            'headline': [],
            'framework': [],
            'model': [],
            'article': [],
            'project': [],
            'other': []
        }
        
        for item in items:
            category = getattr(item, 'category', 'other')
            if category in categorized:
                categorized[category].append(item)
            else:
                categorized['other'].append(item)
        
        # 每个类别按相关性排序
        for category in categorized:
            categorized[category].sort(
                key=lambda x: getattr(x, 'relevance_score', 0),
                reverse=True
            )
        
        return categorized
    
    def _generate_stats(self, items: List, categorized: Dict) -> Dict:
        """
        生成统计数据
        
        Args:
            items: 处理后的条目列表
            categorized: 分类后的字典
            
        Returns:
            统计信息字典
        """
        high_relevance = [
            item for item in items
            if getattr(item, 'relevance_score', 0) >= 8
        ]
        
        actionable = [
            item for item in items
            if getattr(item, 'actionable', False)
        ]
        
        return {
            'total_sources': len(set(getattr(item, 'source', '') for item in items)),
            'total_items': len(items),
            'processed_items': len(items),
            'high_relevance_items': len(high_relevance),
            'actionable_items': len(actionable)
        }
    
    def _save_report(self, content: str, output_path: str):
        """
        保存报告到文件
        
        Args:
            content: 报告内容
            output_path: 输出路径
        """
        try:
            # 确保输出目录存在
            output_file = Path(output_path)
            output_file.parent.mkdir(parents=True, exist_ok=True)
            
            # 写入文件
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            logger.info(f"✓ 报告已保存到: {output_path}")
            
        except Exception as e:
            logger.error(f"保存报告失败: {str(e)}")
    
    def generate_email_body(self, processed_items: List) -> str:
        """
        生成邮件正文（简化版）
        
        Args:
            processed_items: 处理后的条目列表
            
        Returns:
            邮件HTML内容
        """
        top3 = sorted(processed_items, key=lambda x: x.relevance_score, reverse=True)[:3]
        
        html = f"""
        <html>
        <head>
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; }}
                .item {{ margin-bottom: 30px; padding: 15px; background: #f5f5f5; }}
                .title {{ font-size: 18px; font-weight: bold; color: #333; }}
                .meta {{ color: #666; font-size: 14px; margin-top: 5px; }}
                .summary {{ margin-top: 10px; }}
                .impact {{ margin-top: 10px; padding: 10px; background: #fff3cd; }}
            </style>
        </head>
        <body>
            <h1>🚀 本周AI技术头条 (Top 3)</h1>
            <p>生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
        """
        
        for i, item in enumerate(top3, 1):
            html += f"""
            <div class="item">
                <div class="title">{i}. {item.title}</div>
                <div class="meta">来源：{item.source} | <a href="{item.link}">查看详情</a></div>
                <div class="summary">{item.ai_summary}</div>
                <div class="impact"><strong>💡 对你的影响：</strong>{item.impact_analysis}</div>
            </div>
            """
        
        html += """
            <hr>
            <p><small>完整周报请查看附件 | AI Weekly Report Generator</small></p>
        </body>
        </html>
        """
        
        return html

    def _build_paper_radar(self, processed_items: List, used_keys: Set[str]) -> List[Dict[str, Any]]:
        """构建论文雷达列表，优先展示核心AI研究论文"""
        radar_candidates = []
        for item in processed_items:
            source = getattr(item, 'source', '') or ''
            category = getattr(item, 'category', '') or ''
            article_type = getattr(item, 'article_type', '') or ''

            is_research_source = any(keyword in source.lower() for keyword in ["arxiv", "papers with code", "cs.ai", "cs.lg", "neurips", "iclr", "icml"])
            is_research_item = article_type in {"technical", "research"}

            if category in {'framework', 'model', 'project'}:
                continue

            if not (is_research_source or is_research_item):
                continue

            summary = getattr(item, 'summary', '') or getattr(item, 'ai_summary', '') or ''
            personal_note = getattr(item, 'why_matters_to_you', '') or getattr(item, 'impact_analysis', '') or ''

            if not summary:
                # 如果缺少摘要，跳过以确保信噪比
                continue

            dedupe_key = self._make_dedupe_key(item)
            if dedupe_key in used_keys:
                continue

            radar_candidates.append({
                'title': getattr(item, 'title', '未命名论文'),
                'url': getattr(item, 'url', getattr(item, 'link', '')),
                'source': source,
                'summary': summary.strip(),
                'personal_note': personal_note.strip(),
                'published_date': self._format_date(getattr(item, 'published_date', '')),
                'personal_priority': getattr(item, 'personal_priority', getattr(item, 'relevance_score', 0)) or 0,
                '_dedupe_key': dedupe_key,
            })

        radar_candidates.sort(key=lambda x: x['personal_priority'], reverse=True)
        top_items = radar_candidates[:3]

        for entry in top_items:
            used_keys.add(entry['_dedupe_key'])
            entry.pop('_dedupe_key', None)

        return top_items

    @staticmethod
    def _format_date(date_obj: Any) -> str:
        if isinstance(date_obj, datetime):
            return date_obj.strftime('%Y-%m-%d')
        if isinstance(date_obj, str):
            return date_obj[:10]
        return ''

    def _filter_action_items(self, action_items: Dict[str, List], must_read_items: List, top_headlines: List) -> Dict[str, List]:
        """
        过滤行动清单，排除已在必看内容和本周头条中出现的条目
        
        Args:
            action_items: 原始行动清单
            must_read_items: 必看内容列表
            top_headlines: 本周头条列表
            
        Returns:
            过滤后的行动清单
        """
        # 收集已使用的URL
        used_urls = set()
        for item in must_read_items:
            url = getattr(item, 'url', None) or getattr(item, 'link', None)
            if url:
                used_urls.add(url)
        
        for item in top_headlines:
            url = getattr(item, 'url', None) or getattr(item, 'link', None)
            if url:
                used_urls.add(url)
        
        # 过滤must_do和nice_to_have
        filtered_must_do = []
        if action_items.get('must_do'):
            for action in action_items['must_do']:
                action_url = action.get('url', '')
                if action_url and action_url not in used_urls:
                    filtered_must_do.append(action)
        
        filtered_nice_to_have = []
        if action_items.get('nice_to_have'):
            for action in action_items['nice_to_have']:
                action_url = action.get('url', '')
                if action_url and action_url not in used_urls:
                    filtered_nice_to_have.append(action)
        
        return {
            'must_do': filtered_must_do,
            'nice_to_have': filtered_nice_to_have
        }

    def _normalize_source(self, source: str) -> str:
        """
        标准化来源名称，用于来源多样性检查
        
        Args:
            source: 原始来源名称
            
        Returns:
            标准化后的来源名称
        """
        if not source:
            return 'unknown'
        
        source_lower = source.lower()
        
        # 统一arXiv来源
        if 'arxiv' in source_lower:
            return 'arxiv'
        
        # 统一Reddit来源
        if 'reddit' in source_lower or 'r/' in source_lower:
            return 'reddit'
        
        # 统一Hacker News来源
        if 'hacker news' in source_lower or 'hn' in source_lower:
            return 'hacker_news'
        
        # 统一GitHub来源
        if 'github' in source_lower:
            return 'github'
        
        # 返回原始来源（去除版本号等）
        return source.split()[0].split('(')[0].strip()
    
    def _make_dedupe_key(self, item: Any) -> str:
        """
        生成一个唯一的去重键，用于避免重复条目。
        
        Args:
            item: 条目对象
            
        Returns:
            去重键字符串
        """
        return make_dedupe_key(item)
    
    def _is_curated_paper_source(self, source: str) -> bool:
        """
        判断是否为精选论文来源（Hugging Face Papers或Papers with Code）
        
        Args:
            source: 来源名称
            
        Returns:
            是否为精选论文来源
        """
        source_lower = source.lower()
        # 支持完整名称和缩写形式
        return ('hugging face' in source_lower or 
                'hugging' in source_lower or 
                'papers with code' in source_lower or 
                'papers' in source_lower and 'code' in source_lower or
                source_lower.startswith('papers'))

