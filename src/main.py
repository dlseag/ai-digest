"""
AI Weekly Report Generator - Main Entry Point
主程序：整合所有模块生成周报
"""

import argparse
import json
import logging
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import asdict, is_dataclass
import yaml
from dotenv import load_dotenv

# 添加项目根目录到Python路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from src.collectors.rss_collector import RSSCollector
from src.collectors.github_collector import GitHubCollector
from src.collectors.hackernews_collector import HackerNewsCollector
from src.collectors.reddit_collector import RedditCollector
from src.collectors.news_collector import NewsCollector
from src.collectors.producthunt_collector import ProductHuntCollector
from src.collectors.twitter_collector import TwitterCollector
from src.collectors.leaderboard_collector import LeaderboardCollector  # 排行榜采集器
from src.collectors.market_insights_collector import MarketInsightsCollector  # 市场洞察采集器
from src.processors.ai_processor import AIProcessor
from src.processors.ai_processor_batch import AIProcessorBatch  # 批量处理器
from src.generators.report_generator import ReportGenerator
from src.learning.learning_engine import LearningEngine
from src.learning.config_manager import ConfigManager
from src.learning.explicit_feedback import ExplicitFeedbackManager
from src.learning.ab_tester import ABTester, Experiment
from src.storage.feedback_db import OptimizationRecord
from src.utils.emailer import send_digest_email
# 暂时禁用LangGraph相关导入（需要完整实现后再启用）
# from src.agents.briefing_graph import GraphComponents, compile_briefing_graph
# from src.agents.cluster_agent import ClusterAgent
# from src.agents.critique_agent import CritiqueAgent
# from src.agents.differential_agent import DifferentialAgent
# from src.agents.proactive_agent import ProactiveAgent
# from src.agents.state import create_initial_state
# from src.agents.triage_agent import TriageAgent
from src.memory.memory_manager import MemoryManager
from src.memory.user_profile_manager import UserProfileManager

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('weekly_report_generator.log')
    ]
)
logger = logging.getLogger(__name__)


class WeeklyReportGenerator:
    """周报生成器主类"""
    
    def __init__(self, config_dir: Optional[str] = None):
        """
        初始化周报生成器
        
        Args:
            config_dir: 配置文件目录
        """
        # 加载环境变量
        load_dotenv()
        
        # 配置目录
        if config_dir is None:
            config_dir = str(project_root / "config")
        self.config_dir = Path(config_dir)
        
        # 加载配置
        self.sources_config = self._load_yaml(self.config_dir / "sources.yaml")
        raw_user_profile = self._load_yaml(self.config_dir / "user_profile.yaml")
        raw_learning_config = self._load_yaml(self.config_dir / "learning_config.yaml")
        self.learning_config = (raw_learning_config or {}).get("learning", {})
        self.source_preferences = self.learning_config.get("source_preferences", {})
        self.headline_source_limit = int(self.source_preferences.get("max_headlines_per_source", 2))

        self.user_profile_manager = UserProfileManager(
            self.config_dir / "user_profile.yaml",
            profile_data=raw_user_profile,
        )
        self.user_profile = self.user_profile_manager.get_profile()
        self.filtering_preferences = self.user_profile.get("filtering_preferences", {}) or {}

        # 获取API密钥
        self.api_key = os.getenv("POE_API_KEY")
        if not self.api_key:
            logger.warning("POE_API_KEY 环境变量未设置")

        # 初始化各个组件
        self.rss_collector = None
        self.github_collector = None
        self.ai_processor = None
        self.report_generator = None
        self.learning_engine = LearningEngine(
            config=self.learning_config,
            project_root=project_root,
            user_profile_manager=self.user_profile_manager,
            api_key=self.api_key,
        )
        self.explicit_feedback = ExplicitFeedbackManager(self.learning_engine.db)
        self.ab_tester = ABTester(self.learning_engine.db)
        self.email_settings = self._load_email_settings()
        self.ab_experiments: Dict[str, Experiment] = {
            "narrative_clustering_v1": Experiment(
                id="narrative_clustering_v1",
                hypothesis="Narrative clustering提升个性化参与度",
                metric="engagement_score",
                variants={
                    "control": "传统线性摘要",
                    "treatment": "叙事聚类 + RAG-Diff 摘要",
                },
            )
        }
        self.config_manager = ConfigManager(self.config_dir / "sources.yaml")
        self.memory_manager = MemoryManager()
        self.api_key = os.getenv("POE_API_KEY")
        if not self.api_key:
            logger.warning("POE_API_KEY 未配置，LangGraph 工作流将无法调用LLM")
        
        logger.info("=" * 60)
        logger.info("AI Weekly Report Generator 启动")
        logger.info("=" * 60)
    
    def _load_yaml(self, file_path: Path) -> dict:
        """加载YAML配置文件"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f)
        except Exception as e:
            logger.error(f"加载配置文件失败 {file_path}: {str(e)}")
            return {}
    
    def run(
        self,
        days_back: int = 3,
        output_dir: Optional[str] = None,
        learning_only: bool = False,
    ):
        """
        执行完整的周报生成流程
        
        Args:
            days_back: 采集最近N天的内容
            output_dir: 输出目录
        """
        try:
            # 1. 数据采集
            logger.info("\n" + "=" * 60)
            logger.info("步骤 1/5: 数据采集")
            logger.info("=" * 60)
            all_items = self._collect_data(days_back)
            self._dump_collected_items(all_items, days_back, output_dir)
            
            if not all_items:
                logger.warning("未采集到任何数据，退出")
                return
            
            # 1.5 采集排行榜数据（独立于新闻采集）
            leaderboard_info = self._collect_leaderboard()
            
            # 1.6 采集市场洞察（投资趋势、市场分析）
            market_insights = self._collect_market_insights()
            
            # 2. AI处理
            logger.info("\n" + "=" * 60)
            logger.info("步骤 2/5: AI智能处理")
            logger.info("=" * 60)
            processed_items = self._process_with_ai(all_items)
            
            if not processed_items:
                logger.warning("AI处理后无有效数据，退出")
                return
            
            action_items = None
            if not learning_only:
                # 3. 生成行动清单
                logger.info("\n" + "=" * 60)
                logger.info("步骤 3/5: 生成行动清单")
                logger.info("=" * 60)
                action_items = self._generate_action_items(processed_items)
            
            # 3.5 自我学习循环
            learning_results = self._run_learning_cycle(processed_items)
            
            report_path = None
            if not learning_only:
                # 4. 生成周报
                logger.info("\n" + "=" * 60)
                logger.info("步骤 4/5: 生成周报")
                logger.info("=" * 60)
                report_path = self._generate_report(
                    processed_items,
                    action_items or {"must_do": [], "nice_to_have": []},
                    leaderboard_info,
                    market_insights,
                    output_dir,
                    learning_results,
                )
                
                # 完成
                logger.info("\n" + "=" * 60)
                logger.info("✓ 周报生成完成！")
                logger.info(f"✓ 报告路径: {report_path}")
                logger.info("=" * 60)
                self._send_email_if_configured(report_path)
            else:
                logger.info("\n" + "=" * 60)
                logger.info("✓ 已完成学习循环 (learning-only 模式)")
                logger.info("=" * 60)

            self._log_learning_summary(learning_results)
            return report_path
            
        except Exception as e:
            logger.error(f"生成周报失败: {str(e)}", exc_info=True)
            raise

    def run_langgraph(
        self,
        days_back: int = 3,
        output_dir: Optional[str] = None,
        max_iterations: int = 3,
    ) -> Optional[Path]:
        """Experimental workflow powered by LangGraph agents."""

        if not self.api_key:
            raise RuntimeError("POE_API_KEY 未配置，无法运行 LangGraph 工作流")

        logger.info("\n" + "=" * 60)
        logger.info("LangGraph 工作流：开始数据采集")
        logger.info("=" * 60)

        all_items = self._collect_data(days_back)
        self._dump_collected_items(all_items, days_back, output_dir)
        documents = self._prepare_graph_documents(all_items)

        if not documents:
            logger.warning("LangGraph 工作流未获取到有效文档，退出")
            return None

        components = GraphComponents(
            triage_agent=TriageAgent(api_key=self.api_key),
            cluster_agent=ClusterAgent(),
            differential_agent=DifferentialAgent(
                vector_store=self.memory_manager.vector_store,
                api_key=self.api_key,
            ),
            critique_agent=CritiqueAgent(api_key=self.api_key),
            proactive_agent=ProactiveAgent(self.learning_engine.db),
        )

        compiled_graph = compile_briefing_graph(components)
        initial_state = create_initial_state(self.user_profile, max_iterations=max_iterations)
        initial_state["raw_documents"] = documents

        logger.info("\n" + "=" * 60)
        logger.info("LangGraph 工作流：启动智能体图")
        logger.info("=" * 60)

        final_state = compiled_graph.invoke(initial_state)
        report_path = self._write_langgraph_report(final_state, output_dir)

        logger.info("\n" + "=" * 60)
        logger.info("✓ LangGraph 简报生成完成！")
        if report_path:
            logger.info(f"✓ 报告路径: {report_path}")
        logger.info("=" * 60)

        return report_path

    def _dump_collected_items(self, items: list, days_back: int, output_dir: Optional[str]) -> None:
        """将原始采集结果写入日志文件，便于调试"""
        try:
            if output_dir is None:
                dump_dir = project_root / "output"
            else:
                dump_dir = Path(output_dir)

            dump_dir.mkdir(parents=True, exist_ok=True)

            timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
            dump_path = dump_dir / f"collected_items_{timestamp}.json"

            payload = {
                "generated_at": datetime.now().isoformat(),
                "days_back": days_back,
                "total_items": len(items),
                "source_breakdown": self._summarize_sources(items),
                "items": [self._serialize_item(item) for item in items]
            }

            with open(dump_path, 'w', encoding='utf-8') as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)

            logger.info(f"🗂️ 已导出原始采集数据: {dump_path}")

        except Exception as e:
            logger.warning(f"导出原始采集数据失败: {str(e)}")

    def _serialize_item(self, item):
        """将采集结果转换为可JSON序列化的结构"""
        if is_dataclass(item):
            data = asdict(item)
        elif isinstance(item, dict):
            data = dict(item)
        else:
            data = {}
            for attr in dir(item):
                if attr.startswith('_'):
                    continue
                value = getattr(item, attr)
                if callable(value):
                    continue
                data[attr] = value

        return self._normalize_for_json(data)

    def _normalize_for_json(self, value):
        if isinstance(value, datetime):
            return value.isoformat()
        if is_dataclass(value):
            return self._normalize_for_json(asdict(value))
        if isinstance(value, dict):
            return {str(k): self._normalize_for_json(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self._normalize_for_json(v) for v in value]
        if isinstance(value, tuple):
            return [self._normalize_for_json(v) for v in value]
        return value

    def _summarize_sources(self, items: list) -> dict:
        counts = {}
        for item in items:
            source = self._extract_attribute(item, ['source', 'repo_name', 'name']) or 'unknown'
            counts[source] = counts.get(source, 0) + 1
        return counts

    def _prepare_graph_documents(self, items: list) -> List[Dict[str, str]]:
        documents: List[Dict[str, str]] = []
        for index, item in enumerate(items):
            serialized = self._serialize_item(item) or {}
            doc_id = str(
                serialized.get('id')
                or serialized.get('guid')
                or serialized.get('slug')
                or serialized.get('url')
                or f'doc-{index}'
            )
            title = str(
                serialized.get('title')
                or serialized.get('name')
                or serialized.get('headline')
                or serialized.get('repo_name')
                or serialized.get('source')
                or '未命名条目'
            )
            summary = str(
                serialized.get('summary')
                or serialized.get('description')
                or serialized.get('excerpt')
                or ''
            )
            content = str(
                serialized.get('content')
                or serialized.get('body')
                or serialized.get('text')
                or serialized.get('full_text')
                or summary
                or title
            )
            source = str(
                serialized.get('source')
                or serialized.get('feed')
                or serialized.get('repo_name')
                or serialized.get('platform')
                or 'unknown'
            )

            documents.append(
                {
                    'id': doc_id,
                    'title': title.strip(),
                    'summary': summary.strip(),
                    'content': content.strip(),
                    'source': source,
                }
            )
        return documents

    def _extract_attribute(self, item, candidates) -> str:
        if isinstance(item, dict):
            for key in candidates:
                value = item.get(key)
                if value:
                    return str(value)
            return ''

        for key in candidates:
            if hasattr(item, key):
                value = getattr(item, key)
                if value:
                    return str(value)
        return ''
    
    def _collect_data(self, days_back: int) -> list:
        """数据采集阶段"""
        all_items = []
        
        # 采集RSS
        logger.info("\n📡 采集RSS订阅...")
        try:
            rss_sources = self.sources_config.get('rss_feeds', [])
            if rss_sources:
                self.rss_collector = RSSCollector(rss_sources)
                rss_items = self.rss_collector.collect_all(days_back=days_back)
                all_items.extend(rss_items)
                logger.info(f"✓ RSS采集完成: {len(rss_items)} 条目")
            else:
                logger.warning("未配置RSS源")
        except Exception as e:
            logger.error(f"RSS采集失败: {str(e)}")
        
        # 采集GitHub Releases
        logger.info("\n📡 采集GitHub Releases...")
        try:
            github_repos = self.sources_config.get('github_repos', [])
            if github_repos:
                github_token = os.getenv('GITHUB_TOKEN')
                self.github_collector = GitHubCollector(github_repos, github_token)
                
                # 检查API限制
                rate_limit = self.github_collector.check_rate_limit()
                if rate_limit:
                    logger.info(f"GitHub API剩余: {rate_limit.get('remaining', 'N/A')}/{rate_limit.get('limit', 'N/A')}")
                
                github_releases = self.github_collector.collect_all(days_back=days_back)
                all_items.extend(github_releases)
                logger.info(f"✓ GitHub采集完成: {len(github_releases)} 个Release")
            else:
                logger.warning("未配置GitHub仓库")
        except Exception as e:
            logger.error(f"GitHub采集失败: {str(e)}")
        
        # 采集Hacker News
        logger.info("\n📡 采集Hacker News...")
        try:
            hn_config = self.sources_config.get('hacker_news', {})
            if hn_config.get('enabled', False):
                hn_collector = HackerNewsCollector(
                    query_tags=hn_config.get('query_tags', ['AI', 'LLM']),
                    min_points=hn_config.get('min_points', 50)
                )
                hn_items = hn_collector.collect(days_back=days_back)
                all_items.extend(hn_items)
                logger.info(f"✓ HackerNews采集完成: {len(hn_items)} 条目")
            else:
                logger.info("HackerNews采集未启用")
        except Exception as e:
            logger.error(f"HackerNews采集失败: {str(e)}")
        
        # 采集Reddit
        logger.info("\n📡 采集Reddit...")
        try:
            reddit_configs = self.sources_config.get('reddit', [])
            if reddit_configs:
                reddit_collector = RedditCollector(reddit_configs)
                reddit_items = reddit_collector.collect_all(days_back=days_back)
                all_items.extend(reddit_items)
                logger.info(f"✓ Reddit采集完成: {len(reddit_items)} 条目")
            else:
                logger.info("未配置Reddit源")
        except Exception as e:
            logger.error(f"Reddit采集失败: {str(e)}")
        
        # 采集行业新闻
        logger.info("\n📡 采集行业新闻...")
        try:
            news_feeds = self.sources_config.get('news_feeds', [])
            if news_feeds:
                news_collector = NewsCollector(news_feeds)
                news_items = news_collector.collect_all(days_back=days_back)
                all_items.extend(news_items)
                logger.info(f"✓ 新闻采集完成: {len(news_items)} 条目")
            else:
                logger.info("未配置行业新闻源")
        except Exception as e:
            logger.error(f"新闻采集失败: {str(e)}")
        
        # 采集ProductHunt
        logger.info("\n📡 采集ProductHunt...")
        try:
            ph_config = self.sources_config.get('producthunt', {})
            if ph_config:
                ph_collector = ProductHuntCollector(ph_config)
                ph_items = ph_collector.collect(days_back=days_back)
                all_items.extend(ph_items)
                logger.info(f"✓ ProductHunt采集完成: {len(ph_items)} 条目")
            else:
                logger.info("未配置ProductHunt")
        except Exception as e:
            logger.error(f"ProductHunt采集失败: {str(e)}")
        
        # 采集Twitter信号
        logger.info("\n📡 采集Twitter信号...")
        try:
            twitter_config = self.sources_config.get('twitter', {})
            if twitter_config.get('enabled', False):
                twitter_collector = TwitterCollector(twitter_config)
                twitter_items = twitter_collector.collect()
                all_items.extend(twitter_items)
                logger.info(f"✓ Twitter采集完成: {len(twitter_items)} 条目")
            else:
                logger.info("Twitter采集未启用")
        except Exception as e:
            logger.error(f"Twitter采集失败: {str(e)}")
        
        logger.info(f"\n📊 数据采集总计: {len(all_items)} 条目")
        return all_items
    
    def _collect_leaderboard(self) -> dict:
        """采集LMSYS排行榜数据"""
        try:
            logger.info("\n🏆 采集LLM性能排行榜...")
            leaderboard_collector = LeaderboardCollector()
            leaderboard_data = leaderboard_collector.collect(top_n=10)
            update_time = leaderboard_collector.get_update_time()
            
            logger.info(f"✓ 排行榜采集完成: {len(leaderboard_data)} 个模型")
            
            return {
                'data': leaderboard_data,
                'update_time': update_time
            }
        except Exception as e:
            logger.error(f"排行榜采集失败: {str(e)}")
            return {
                'data': [],
                'update_time': ''
            }
    
    def _collect_market_insights(self) -> list:
        """采集市场洞察数据"""
        try:
            logger.info("\n📈 采集市场洞察...")
            
            # 从配置文件获取市场洞察源（如果有配置的话）
            market_sources = self.sources_config.get('market_insights', [])
            
            market_collector = MarketInsightsCollector(market_sources if market_sources else None)
            all_insights = market_collector.collect(days_back=30)
            
            # 获取Top 3最重要的洞察
            top_insights = market_collector.get_top_insights(all_insights, top_n=3)
            
            logger.info(f"✓ 市场洞察采集完成: {len(all_insights)} 条，筛选 Top {len(top_insights)}")
            
            # 转换为字典格式（模板需要）
            return [insight.to_dict() for insight in top_insights]
            
        except Exception as e:
            logger.error(f"市场洞察采集失败: {str(e)}")
            return []
    
    def _process_with_ai(self, items: list) -> list:
        """AI处理阶段 - 使用批量处理优化"""
        try:
            api_key = os.getenv('POE_API_KEY')
            if not api_key:
                logger.error("未找到POE_API_KEY环境变量")
                return []
            
            # 从环境变量获取模型名称，默认使用Haiku
            model = os.getenv('DEVELOPER_MODEL', 'Claude-Sonnet-4.5')
            
            # 使用批量处理器（新方案：1次API调用代替158次）
            batch_processor = AIProcessorBatch(
                api_key=api_key,
                model_name=model,
                user_profile=self.user_profile,
                explicit_feedback_manager=self.explicit_feedback,
            )
            
            logger.info(f"🚀 批量AI处理模式: {len(items)} 条 → 筛选 Top 25")
            logger.info("（1次API调用，预计1-2分钟）")
            
            # 批量筛选和分析（一次性完成）
            processed_items = batch_processor.batch_select_and_analyze(
                all_items=items,
                top_n=25  # 只筛选最重要的25条
            )

            self._log_ab_metric(processed_items)
            
            # 显示相关性分布
            high_relevance = len([i for i in processed_items if i.relevance_score >= 8])
            medium_relevance = len([i for i in processed_items if 5 <= i.relevance_score < 8])
            low_relevance = len([i for i in processed_items if i.relevance_score < 5])
            
            logger.info(f"\n📊 相关性分布:")
            logger.info(f"  - 高相关 (≥8分): {high_relevance} 条")
            logger.info(f"  - 中相关 (5-7分): {medium_relevance} 条")
            logger.info(f"  - 低相关 (<5分): {low_relevance} 条")
            
            # 显示分类分布
            from collections import Counter
            category_dist = Counter([i.category for i in processed_items])
            logger.info(f"\n📂 分类分布:")
            for category, count in category_dist.most_common():
                logger.info(f"  - {category}: {count} 条")
            
            return processed_items
            
        except Exception as e:
            logger.error(f"批量AI处理失败: {str(e)}")
            logger.info("尝试降级到传统处理模式...")
            
            # 降级方案：使用传统逐条处理（前30条）
            try:
                self.ai_processor = AIProcessor(
                    api_key=api_key,
                    user_profile=self.user_profile,
                    model=model,
                    explicit_feedback_manager=self.explicit_feedback,
                )
                logger.info(f"使用传统模式处理前30条...")
                processed_fallback = self.ai_processor.process_batch(items[:30])
                self._log_ab_metric(processed_fallback)
                return processed_fallback
            except Exception as fallback_error:
                logger.error(f"降级处理也失败: {str(fallback_error)}")
                return []
    
    def _generate_action_items(self, processed_items: list) -> dict:
        """生成行动清单（去重：排除已在必看内容中的新闻）"""
        try:
            # 简化版：从处理结果中提取actionable items
            filtering_prefs = self.filtering_preferences
            ignore_keywords = [
                keyword.lower() for keyword in filtering_prefs.get("ignore_keywords", [])
            ]
            minimum_optional_score = filtering_prefs.get("minimum_optional_score", 6)

            # 🔑 关键改进：先识别出"必看内容"（personal_priority >= 8）
            must_read_urls = set()
            for item in processed_items:
                if item.personal_priority >= 8:  # 降低阈值从9到8
                    must_read_urls.add(item.url)
            
            logger.info(f"📌 识别到 {len(must_read_urls)} 条必看内容，将从建议行动中排除")

            must_do = []
            nice_to_have = []
            
            for item in processed_items:
                # 跳过已经在"必看内容"中的新闻
                if item.url in must_read_urls:
                    logger.debug(f"跳过重复新闻（已在必看内容）: {item.title}")
                    continue
                
                title_lower = (item.title or "").lower()
                if any(keyword in title_lower for keyword in ignore_keywords):
                    logger.debug(f"过滤掉低价值内容: {item.title}")
                    continue

                if not item.actionable:
                    continue

                impact_text = item.impact_analysis or item.why_matters_to_you or ""

                if item.relevance_score is None:
                    continue

                if item.relevance_score >= 8:
                    must_do.append({
                        'title': item.title,
                        'action': impact_text,
                        'source': item.source,
                        'url': item.url
                    })
                elif item.relevance_score >= minimum_optional_score:
                    nice_to_have.append({
                        'title': item.title,
                        'action': impact_text,
                        'source': item.source,
                        'url': item.url
                    })
            
            action_items = {
                'must_do': must_do[:5],  # 最多5项
                'nice_to_have': nice_to_have[:5]  # 最多5项
            }
            
            logger.info(f"\n📋 行动清单:")
            logger.info(f"  - 必做任务: {len(action_items['must_do'])} 项")
            logger.info(f"  - 可选任务: {len(action_items['nice_to_have'])} 项")
            
            return action_items
            
        except Exception as e:
            logger.error(f"生成行动清单失败: {str(e)}")
            return {'must_do': [], 'nice_to_have': []}
    
    def _generate_report(
        self,
        processed_items: list,
        action_items: dict,
        leaderboard_info: dict,
        market_insights: list,
        output_dir: Optional[str] = None,
        learning_results: Optional[dict] = None,
    ) -> str:
        """生成报告"""
        try:
            self.report_generator = ReportGenerator(
                headline_source_limit=self.headline_source_limit
            )
            
            # 确定输出路径
            if output_dir is None:
                output_dir = str(project_root / "output")
            
            os.makedirs(output_dir, exist_ok=True)
            
            # 生成文件名
            date_str = datetime.now().strftime('%Y-%m-%d')
            output_path = os.path.join(output_dir, f"weekly_report_{date_str}.md")
            
            # 生成报告
            logger.info(f"📝 生成Markdown报告...")
            report = self.report_generator.generate_report(
                processed_items=processed_items,
                action_items=action_items,
                leaderboard_data=leaderboard_info.get('data', []),
                leaderboard_update_time=leaderboard_info.get('update_time', ''),
                market_insights=market_insights,
                output_path=output_path,
                learning_results=learning_results or {},
            )
            
            # 显示统计
            logger.info(f"\n📄 报告统计:")
            logger.info(f"  - 总字数: {len(report)} 字符")
            logger.info(f"  - 输出路径: {output_path}")
            
            return output_path
            
        except Exception as e:
            logger.error(f"生成报告失败: {str(e)}")
            raise

    def _run_learning_cycle(self, processed_items: list) -> dict:
        """运行自我学习循环"""
        try:
            logger.info("\n🧠 运行自我学习循环...")
            is_weekly = self._is_weekly_report_day()
            learning_results = self.learning_engine.run_cycle(processed_items, is_weekly=is_weekly)
            logger.info("✓ 自我学习循环完成。")
            return learning_results
        except Exception as e:
            logger.error(f"自我学习循环失败: {str(e)}")
            return {
                "auto_applied": [],
                "require_review": [],
                "insights": [],
                "priority_adjustments": [],
                "discovery": {},
                "models": {},
                "weekly_summary": None,
                "is_weekly": False,
            }

    def _log_learning_summary(self, learning_results: dict) -> None:
        """记录学习引擎的总结"""
        if not learning_results:
            logger.info("\n📚 学习引擎未运行或无结果。")
            return

        auto_applied = learning_results.get("auto_applied", [])
        require_review = learning_results.get("require_review", [])
        discovery = learning_results.get("discovery", {})
        models = learning_results.get("models", {})

        logger.info("\n📚 学习引擎总结:")
        logger.info(f"  - 自动应用优化: {len(auto_applied)} 项")
        logger.info(f"  - 待审查建议: {len(require_review)} 项")
        if discovery:
            logger.info(
                "  - 新信息源评估: %s 个候选 (自动添加 %s 个)",
                discovery.get("evaluated", 0),
                len(discovery.get("auto_add_candidates", [])),
            )
        if models:
            logger.info(
                "  - 新模型评估: %s 个 (重点关注 %s 个)",
                models.get("evaluated", 0),
                len(models.get("flagged", [])),
            )

        if learning_results.get("weekly_summary"):
            summary = learning_results["weekly_summary"]
            logger.info(
                "  - 本周新增信息源: %s 个，移除信息源: %s 个",
                len(summary.get("sources_added", [])),
                len(summary.get("sources_removed", [])),
            )

    def _is_weekly_report_day(self) -> bool:
        weekly_cfg = (self.learning_config or {}).get("weekly_summary", {})
        target_day = weekly_cfg.get("day_of_week", 0)
        try:
            target_day = int(target_day)
        except (TypeError, ValueError):
            target_day = 0
        return datetime.now().weekday() == target_day

    # ------------------------------------------------------------------
    # CLI helpers
    # ------------------------------------------------------------------
    def list_recommendations(self) -> None:
        threshold = (self.learning_config.get("source_discovery", {}) or {}).get(
            "min_quality_for_recommendation", 7.0
        )
        candidates = self.learning_engine.db.get_pending_sources(threshold)
        if not candidates:
            print("暂无待审批的新增信息源。")
            return

        print("待审批信息源列表:\n")
        for idx, candidate in enumerate(candidates, 1):
            print(
                f"{idx}. {candidate.get('name') or candidate.get('url')}"
                f" | 类型: {candidate.get('type')}"
                f" | 质量: {candidate.get('quality_score', '?')}/10"
                f" | 链接: {candidate.get('url')}"
            )

    def apply_recommendation(self, identifier: str) -> None:
        candidates = self.learning_engine.db.get_pending_sources(0)
        target = self._find_candidate(candidates, identifier)
        if not target:
            logger.error("未找到匹配的候选信息源：%s", identifier)
            return

        if self.config_manager.add_source(target):
            self.config_manager.save()
            logger.info("已更新sources.yaml，新增信息源：%s", target.get("name") or target.get("url"))
        else:
            logger.info("信息源已存在于配置中，跳过写入。")

        self.learning_engine.db.update_discovered_source_status(target.get("url"), "approved")
        self.learning_engine.db.log_optimization(
            OptimizationRecord(
                optimization_type="add_source_manual",
                target=target.get("url"),
                details={"name": target.get("name"), "type": target.get("type")},
            )
        )

    def reject_recommendation(self, identifier: str) -> None:
        candidates = self.learning_engine.db.get_pending_sources(0)
        target = self._find_candidate(candidates, identifier)
        if not target:
            logger.error("未找到匹配的候选信息源：%s", identifier)
            return
        self.learning_engine.db.update_discovered_source_status(target.get("url"), "rejected")
        logger.info("已拒绝信息源：%s", target.get("name") or target.get("url"))

    def print_learning_summary(self) -> None:
        summary = self.learning_engine.generate_weekly_summary()
        print("学习引擎摘要：")
        print(f"- 本周新增信息源：{len(summary.get('sources_added', []))}")
        print(f"- 本周停用信息源：{len(summary.get('sources_removed', []))}")
        print(f"- 本周模型评估：{len(summary.get('models_evaluated', []))}\n")

    def _find_candidate(self, candidates: list, identifier: str) -> Optional[dict]:
        slug = self._slugify(identifier)
        for candidate in candidates:
            url = candidate.get("url", "")
            name = candidate.get("name", "")
            if identifier == url or identifier == name:
                return candidate
            if self._slugify(url) == slug or self._slugify(name) == slug:
                return candidate
        return None

    def _slugify(self, value: str) -> str:
        return "".join(ch.lower() if ch.isalnum() else "-" for ch in value or "").strip("-")

    def _write_langgraph_report(
        self,
        state: Dict,
        output_dir: Optional[str] = None,
    ) -> Optional[Path]:
        output_path = Path(output_dir) if output_dir else project_root / "output"
        output_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        report_path = output_path / f"langgraph_report_{timestamp}.md"

        briefing = state.get("final_briefing") or state.get("briefing_draft") or ""
        differential = state.get("differential_analysis", []) or []
        suggestions = state.get("proactive_suggestions", []) or []

        lines: List[str] = [
            "# 🧠 AI Intelligence Briefing (LangGraph Experimental)",
            "",
        ]

        if briefing:
            lines.append(briefing)
            if not briefing.endswith("\n"):
                lines.append("")
        else:
            lines.append("（当前尚未生成简报草稿）\n")

        if differential:
            lines.append("## 🔍 差异分析 (RAG-Diff)")
            for idx, insight in enumerate(differential, start=1):
                lines.append(f"### 主题 {idx}")
                if insight.get("new_findings"):
                    lines.append("- 新发现：" + "；".join(insight["new_findings"]))
                if insight.get("updates"):
                    lines.append("- 更新：" + "；".join(insight["updates"]))
                if insight.get("contradictions"):
                    lines.append("- 矛盾：" + "；".join(insight["contradictions"]))
                if insight.get("meta_analysis"):
                    lines.append(f"- 重要性：{insight['meta_analysis']}")
                lines.append("")

        if suggestions:
            lines.append("## 🚀 主动建议")
            for suggestion in suggestions:
                title = suggestion.get("title", "建议")
                reason = suggestion.get("reason", "")
                action = suggestion.get("action", "")
                related = suggestion.get("related_topics", [])
                lines.append(f"- **{title}**")
                if reason:
                    lines.append(f"  - 原因：{reason}")
                if action:
                    lines.append(f"  - 行动：{action}")
                if related:
                    lines.append(f"  - 关联主题：{', '.join(related)}")
                lines.append("")

        with open(report_path, "w", encoding="utf-8") as handle:
            handle.write("\n".join(lines))

        return report_path

    def _log_ab_metric(self, processed_items: list) -> None:
        experiment = self.ab_experiments.get("narrative_clustering_v1")
        if not experiment or not processed_items:
            return

        variant = os.getenv("AB_NARRATIVE_VARIANT")
        if not variant:
            variant = "treatment"

        try:
            engagement_score = sum(
                getattr(item, "personal_priority", 0) for item in processed_items
            ) / len(processed_items)
        except Exception:
            engagement_score = 0.0

        self.ab_tester.log_metric(
            experiment,
            variant,
            engagement_score,
        )

    def _load_email_settings(self) -> Dict[str, Any]:
        recipients = os.getenv("DIGEST_EMAIL_TO") or "davidzheng0119@163.com"
        parsed_recipients = [addr.strip() for addr in recipients.split(",") if addr.strip()]

        settings = {
            "recipients": parsed_recipients,
            "smtp_host": os.getenv("DIGEST_SMTP_HOST"),
            "smtp_port": int(os.getenv("DIGEST_SMTP_PORT", "465")),
            "smtp_user": os.getenv("DIGEST_SMTP_USER"),
            "smtp_pass": os.getenv("DIGEST_SMTP_PASS"),
            "sender": os.getenv("DIGEST_EMAIL_FROM"),
        }

        required_fields = ("smtp_host", "smtp_user", "smtp_pass")
        settings["enabled"] = all(settings.get(field) for field in required_fields)
        return settings

    def _compose_email_body(self, report_path: Path) -> str:
        text = report_path.read_text(encoding="utf-8")
        snippet_limit = int(os.getenv("DIGEST_EMAIL_BODY_LIMIT", "8000"))
        if len(text) > snippet_limit:
            return text[:snippet_limit] + "\n\n（内容较长，完整内容见附件）"
        return text

    def _send_email_if_configured(self, report_path: Optional[str]) -> None:
        if not report_path:
            return

        settings = self.email_settings
        if not settings.get("enabled"):
            logger.info("邮件通知未启用，缺少SMTP配置，已跳过发送。")
            return

        report_path = Path(report_path)
        try:
            subject = f"AI 情报简报 | {datetime.now().strftime('%Y-%m-%d')}"
            body = self._compose_email_body(report_path)
            send_digest_email(
                report_path,
                subject,
                settings.get("recipients", []),
                smtp_host=settings["smtp_host"],
                smtp_port=settings.get("smtp_port", 465),
                smtp_user=settings["smtp_user"],
                smtp_password=settings["smtp_pass"],
                sender=settings.get("sender"),
                body_text=body,
            )
        except Exception as e:
            logger.error("发送简报邮件失败: %s", e)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="AI Digest Report Generator")
    parser.add_argument("--days-back", type=int, default=3, help="采集最近N天的数据")
    parser.add_argument("--list-recommendations", action="store_true", help="列出待审批的信息源")
    parser.add_argument("--apply-recommendation", help="批准并加入配置的新信息源（输入URL或名称）")
    parser.add_argument("--reject-recommendation", help="拒绝候选信息源（输入URL或名称）")
    parser.add_argument("--learning-summary", action="store_true", help="打印学习引擎的周度摘要")
    parser.add_argument("--learning-only", action="store_true", help="仅运行学习循环，跳过周报生成")
    parser.add_argument("--use-langgraph", action="store_true", help="使用 LangGraph 工作流生成实验性简报")
    parser.add_argument("--ab-summary", action="store_true", help="输出当前AB测试统计摘要")
    args = parser.parse_args()

    try:
        generator = WeeklyReportGenerator()
        
        if args.list_recommendations:
            generator.list_recommendations()
            return
        if args.apply_recommendation:
            generator.apply_recommendation(args.apply_recommendation)
            return
        if args.reject_recommendation:
            generator.reject_recommendation(args.reject_recommendation)
            return
        if args.learning_summary:
            generator.print_learning_summary()
            return
        if args.ab_summary:
            generator.print_ab_summary()
            return

        if args.use_langgraph:
            if args.learning_only:
                logger.warning("LangGraph 模式暂不支持 learning-only 参数，将忽略该选项。")
            generator.run_langgraph(days_back=args.days_back)
            return

        generator.run(days_back=args.days_back, learning_only=args.learning_only)
        
    except KeyboardInterrupt:
        logger.info("\n用户中断执行")
        sys.exit(0)
    except Exception as e:
        logger.error(f"程序执行失败: {str(e)}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

