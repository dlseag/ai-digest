"""
AI Weekly Report Generator - Main Entry Point
主程序：整合所有模块生成周报
"""

import argparse
import json
import logging
import os
import signal
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
from src.learning.feedback_learning import FeedbackLearningEngine
from src.storage.feedback_db import OptimizationRecord
from src.utils.emailer import send_digest_email
from src.graph.briefing_graph import BriefingState, compile_briefing_graph
from src.memory.memory_manager import MemoryManager
from src.memory.user_profile_manager import UserProfileManager
from src.agents.quick_filter_agent import QuickFilterAgent
from src.agents.action_agent import ActionAgent
from src.agents.tool_executor import ToolExecutor
from src.integrations.notion_sync import NotionSyncService, build_notion_title

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
            ),
            "scoring_threshold_v1": Experiment(
                id="scoring_threshold_v1",
                hypothesis="提高 optional 阈值能提升建议质量",
                metric="engagement_score",
                variants={
                    "control": "optional_threshold_6",
                    "treatment": "optional_threshold_7",
                },
            ),
        }
        self.ab_variants: Dict[str, str] = {}
        user_identifier = (
            self.user_profile.get("user_info", {}).get("email")
            or self.user_profile.get("user_info", {}).get("name")
            or "default_user"
        )
        for exp_id, experiment in self.ab_experiments.items():
            try:
                assigned = self.ab_tester.assign_variant(user_identifier, experiment)
            except Exception:
                assigned = "control"
            self.ab_variants[exp_id] = assigned

        override_variant = os.getenv("AB_NARRATIVE_VARIANT")
        if override_variant:
            self.ab_variants["narrative_clustering_v1"] = override_variant

        self.config_manager = ConfigManager(self.config_dir / "sources.yaml")
        self.memory_manager = MemoryManager()
        self.notion_sync = NotionSyncService()
        
        # 初始化 QuickFilterAgent（如果 API key 可用）
        self.quick_filter_agent: Optional[QuickFilterAgent] = None
        if self.api_key:
            try:
                model = os.getenv("QUICK_FILTER_MODEL", "Claude-Haiku-4.5")
                max_batch = int(os.getenv("QUICK_FILTER_BATCH", "12"))
                min_score = int(os.getenv("QUICK_FILTER_MIN_SCORE", "5"))
                self.quick_filter_agent = QuickFilterAgent(
                    api_key=self.api_key,
                    model_name=model,
                    max_batch_size=max_batch,
                    min_score_keep=min_score,
                )
                logger.debug("✓ QuickFilterAgent 初始化成功")
            except Exception as e:
                logger.warning(f"QuickFilterAgent 初始化失败: {e}，将使用降级方案")
        else:
            logger.debug("QuickFilterAgent 未初始化：缺少 POE_API_KEY")

        self.briefing_graph = compile_briefing_graph(self)
        
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
        """执行完整的周报生成流程（基于 LangGraph 编排）"""
        params: Dict[str, Any] = {
            "days_back": days_back,
            "output_dir": output_dir,
            "learning_only": learning_only,
        }

        initial_state: BriefingState = {
            "params": params,
            "errors": [],
        }

        logger.info("\n" + "=" * 60)
        logger.info("启动 LangGraph 工作流")
        logger.info("=" * 60)

        try:
            final_state = self.briefing_graph.invoke(initial_state)
        except Exception as exc:  # pragma: no cover - safety net
            logger.error(f"生成周报失败: {exc}", exc_info=True)
            raise

        errors = final_state.get("errors") or []
        for message in errors:
            logger.error(message)

        learning_results = final_state.get("learning_results") or {}
        if learning_results:
            self._log_learning_summary(learning_results)

        report_path_value = final_state.get("report_path")
        if learning_only:
            logger.info("\n" + "=" * 60)
            logger.info("✓ 已完成学习循环 (learning-only 模式)")
            logger.info("=" * 60)
        elif report_path_value:
            logger.info("\n" + "=" * 60)
            logger.info("✓ 周报生成完成！")
            logger.info(f"✓ 报告路径: {report_path_value}")
            logger.info("=" * 60)
        else:
            logger.warning("本次运行未生成周报。")

        return Path(report_path_value) if report_path_value else None

    def run_langgraph(
        self,
        days_back: int = 3,
        output_dir: Optional[str] = None,
        max_iterations: int = 3,
    ) -> Optional[Path]:
        """
        [已废弃] 兼容旧参数，当前与 run() 等价。
        
        注意：默认 run() 方法已使用 LangGraph，此方法仅为向后兼容保留。
        建议直接使用 run() 方法。
        """
        logger.warning("run_langgraph() 已废弃，默认 run() 方法已使用 LangGraph。请直接使用 run()。")
        return self.run(days_back=days_back, output_dir=output_dir, learning_only=False)

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
            # 过滤 enabled=false 的源
            enabled_rss_sources = [s for s in rss_sources if s.get('enabled', True)]
            logger.info(f"RSS源: {len(enabled_rss_sources)} 个已启用 / {len(rss_sources)} 个总计")
            
            if enabled_rss_sources:
                self.rss_collector = RSSCollector(enabled_rss_sources)
                rss_items = self.rss_collector.collect_all(days_back=days_back)
                all_items.extend(rss_items)
                logger.info(f"✓ RSS采集完成: {len(rss_items)} 条目")
            else:
                logger.warning("未配置启用的RSS源")
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
    

    def _collect_market_insights(self) -> list:
        """采集市场洞察数据"""
        try:
            logger.info("\n📈 采集市场洞察...")
            market_sources = self.sources_config.get('market_insights', [])
            market_collector = MarketInsightsCollector(market_sources if market_sources else None)
            all_insights = market_collector.collect(days_back=30)
            top_insights = market_collector.get_top_insights(all_insights, top_n=3)
            logger.info(f"✓ 市场洞察采集完成: {len(all_insights)} 条，筛选 Top {len(top_insights)}")
            return [insight.to_dict() for insight in top_insights]
        except Exception as e:
            logger.error(f"市场洞察采集失败: {str(e)}")
            return []

    
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
    
    def _quick_filter_items(self, items: list) -> tuple[list, dict]:
        """Use a lightweight LLM pass to filter obvious noise before heavy processing."""
        total = len(items)
        if total == 0:
            return [], {"input_total": 0, "kept": 0, "dropped": 0, "avg_score": 0.0, "strategy": "empty"}

        # 如果 QuickFilterAgent 未初始化（缺少 API key 或初始化失败），使用降级方案
        if self.quick_filter_agent is None:
            logger.debug("⚠️ 快速初评跳过：QuickFilterAgent 未初始化")
            return list(items), {
                "input_total": total,
                "kept": total,
                "dropped": 0,
                "avg_score": 8.0,
                "strategy": "no_agent",
            }

        try:
            top_k = int(os.getenv("QUICK_FILTER_TOP_K", "60"))
            filtered, stats = self.quick_filter_agent.filter_items(items, top_k=top_k)
            logger.info(
                "⚡ 快速初评: 输入=%s, 保留=%s, 丢弃=%s, 平均分=%s (策略=%s)",
                stats.get("input_total"),
                stats.get("kept"),
                stats.get("dropped"),
                stats.get("avg_score"),
                stats.get("strategy"),
            )
            if stats.get("dropped"):
                try:
                    self.explicit_feedback.record_auto_feedback(
                        rule=f"快速初评丢弃 {stats.get('dropped')} 条低分内容",
                        desired_behavior="保留与LLM工程密切相关且得分较高的条目。",
                        context=str(stats),
                        correction_type="quick_filter",
                    )
                except Exception:
                    logger.debug("记录自动反馈失败，已忽略")
            return filtered, stats
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.error("快速初评失败: %s", exc, exc_info=True)
            return list(items), {
                "input_total": total,
                "kept": total,
                "dropped": 0,
                "avg_score": 8.0,
                "strategy": "exception",
            }

    def _is_release_candidate(self, item: Any) -> bool:
        category = (getattr(item, "category", "") or "").lower()
        if category in {"framework", "model"}:
            return True

        title = (getattr(item, "title", "") or "").lower()
        if "release" in title or title.startswith("v"):
            return True

        source = (getattr(item, "source", "") or "").lower()
        url = (getattr(item, "url", getattr(item, "link", "")) or "").lower()

        # 检查是否为 GitHub Release（通过 URL 判断）
        if "/releases/" in url or "/tag/" in url:
            return True

        return False

    def _should_promote_release(self, item: Any) -> bool:
        if not self._is_release_candidate(item):
            return True

        # 过滤纯版本号的 Release（如 b7071, v1.80.0.rc.1, 1.5.0）
        title = (getattr(item, "title", "") or "").strip()
        import re
        # 匹配纯版本号模式：b7071, v1.2.3, 1.2.3, v1.2.3-rc.1 等
        version_pattern = r'^[bv]?\d+(\.\d+)*(-[a-z]+(\.\d+)?)?$'
        if re.match(version_pattern, title, re.IGNORECASE):
            logger.debug(f"⏭ 跳过纯版本号 Release: {title}")
            return False

        tags = getattr(item, "tags", None) or []
        if any(tag in {"critical_release", "force_release"} for tag in tags):
            return True

        text = " ".join(
            part.lower()
            for part in [getattr(item, "title", ""), getattr(item, "summary", ""), getattr(item, "description", "")]
            if part
        )

        keyword_config = (
            self.user_profile.get("report_generation_rules", {}).get("critical_release_keywords")
            if hasattr(self, "user_profile") else None
        )
        critical_keywords = keyword_config or ["security", "紧急", "critical", "漏洞", "cve", "重大", "breaking"]

        if any(keyword in text for keyword in critical_keywords):
            return True

        return False

    def _expand_long_articles(self, items: list) -> list:
        """Split very long summaries into smaller chunks so the batch prompt stays within limits."""
        import re
        from dataclasses import replace

        expanded: List[Any] = []
        max_chars = int(os.getenv('LONG_ARTICLE_MAX_CHARS', '1600'))
        overlap = int(os.getenv('LONG_ARTICLE_OVERLAP', '200'))

        for item in items:
            summary = self._extract_attribute(item, ['summary', 'description']) or ''
            if len(summary) <= max_chars:
                expanded.append(item)
                continue

            sentences = re.split(r'(?<=[。！？!?\.])\s+', summary)
            chunks: List[str] = []
            current = ''
            for sentence in sentences:
                sentence = sentence.strip()
                if not sentence:
                    continue
                candidate = f"{current} {sentence}".strip() if current else sentence
                if len(candidate) <= max_chars:
                    current = candidate
                else:
                    if current:
                        chunks.append(current.strip())
                    current = sentence
            if current:
                chunks.append(current.strip())

            if not chunks:
                expanded.append(item)
                continue

            merged: List[str] = []
            for chunk in chunks:
                if not merged:
                    merged.append(chunk)
                    continue
                if len(chunk) < overlap:
                    merged[-1] = f"{merged[-1]} {chunk}".strip()
                else:
                    merged.append(chunk)

            original_title = self._extract_attribute(item, ['title', 'name']) or 'Long Article'
            for part_idx, chunk in enumerate(merged, start=1):
                new_title = f"{original_title} [Part {part_idx}]" if len(merged) > 1 else original_title
                try:
                    if hasattr(item, '__dataclass_fields__'):
                        new_item = replace(item, summary=chunk)
                        if hasattr(new_item, 'content'):
                            setattr(new_item, 'content', chunk)
                        if hasattr(new_item, 'title'):
                            setattr(new_item, 'title', new_title)
                    elif isinstance(item, dict):
                        new_item = dict(item)
                        new_item['summary'] = chunk
                        new_item['title'] = new_title
                    else:
                        new_item = item
                except Exception:
                    new_item = item
                expanded.append(new_item)

        return expanded
    
    def _process_with_ai(self, items: list) -> list:
        """AI处理阶段 - 使用批量处理优化"""
        try:
            api_key = os.getenv('POE_API_KEY')
            if not api_key:
                logger.error("未找到POE_API_KEY环境变量")
                return []
            
            # 从环境变量获取模型名称，默认使用Sonnet 4.5
            model = os.getenv('DEVELOPER_MODEL', 'Claude-Sonnet-4.5')
            
            # 使用批量处理器（新方案：1次API调用代替158次）
            batch_processor = AIProcessorBatch(
                api_key=api_key,
                model_name=model,
                user_profile=self.user_profile,
                explicit_feedback_manager=self.explicit_feedback,
            )
            
            logger.info(f"🚀 批量AI处理模式: {len(items)} 条 → 筛选 Top 60")
            logger.info(f"📋 使用模型: {model}")
            logger.info("（1次API调用，预计2-3分钟）")

            expanded_items = self._expand_long_articles(items)
            if len(expanded_items) != len(items):
                logger.info("🧵 长文分段: %s → %s", len(items), len(expanded_items))

            if not expanded_items:
                logger.warning("长文分段后没有可处理的条目")
                return []

            # 选项1: 增加AI处理数量到60条（确保覆盖论文）
            top_n = min(60, len(expanded_items))
            processed_items = batch_processor.batch_select_and_analyze(
                all_items=expanded_items,
                top_n=top_n
            )

            release_debug = []
            for processed_item in processed_items:
                is_release = self._is_release_candidate(processed_item)
                promote_release = self._should_promote_release(processed_item)
                setattr(processed_item, "is_release", is_release)
                setattr(processed_item, "promote_release", promote_release)
                if is_release:
                    release_debug.append(f"{processed_item.title}=>{promote_release}")

            if release_debug:
                logger.info("🧮 Release过滤: %s", ", ".join(release_debug))

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
            
            # 降级方案：使用传统逐条处理（选项1+2：处理60条，论文优先）
            try:
                self.ai_processor = AIProcessor(
                    api_key=api_key,
                    user_profile=self.user_profile,
                    model=model,
                    explicit_feedback_manager=self.explicit_feedback,
                )
                logger.info("⚠️ 批量模式失败，切换至传统处理（Top 60，论文优先）...")

                # 选项1: 扩大处理数量到60条
                fallback_pool = (
                    expanded_items if 'expanded_items' in locals() and expanded_items else items
                )
                top_n_fallback = min(60, len(fallback_pool))

                # 选项2: 为论文类别单独处理，确保至少15篇论文
                paper_items = []
                news_items = []
                for item in fallback_pool:
                    category = getattr(item, 'category', item.get('category', '') if hasattr(item, 'get') else '')
                    if category == 'paper':
                        paper_items.append(item)
                    else:
                        news_items.append(item)

                # 论文内部优先级：Hugging Face Papers > Papers with Code > arXiv
                def get_paper_priority(item):
                    source = getattr(item, 'source', item.get('source', '') if hasattr(item, 'get') else '').lower()
                    if 'hugging face' in source:
                        return 3
                    elif 'papers with code' in source:
                        return 2
                    elif 'arxiv' in source:
                        return 1
                    else:
                        return 0
                
                # 按来源优先级排序论文
                paper_items.sort(key=get_paper_priority, reverse=True)

                paper_quota = min(15, len(paper_items))
                news_quota = top_n_fallback - paper_quota
                prioritized_items = paper_items[:paper_quota] + news_items[:news_quota]

                # 统计论文来源
                paper_sources = {}
                for p in paper_items[:paper_quota]:
                    source = getattr(p, 'source', 'Unknown')
                    paper_sources[source] = paper_sources.get(source, 0) + 1

                logger.info(
                    "📄 传统模式优先处理: %s 篇论文 + %s 条新闻",
                    len(paper_items[:paper_quota]),
                    len(news_items[:news_quota]),
                )
                if paper_sources:
                    logger.info(f"  论文来源: {', '.join([f'{k}: {v}' for k, v in sorted(paper_sources.items(), key=lambda x: x[1], reverse=True)])}")

                processed_fallback = self.ai_processor.process_batch(prioritized_items)

                for processed_item in processed_fallback:
                    is_release = self._is_release_candidate(processed_item)
                    promote_release = self._should_promote_release(processed_item)
                    setattr(processed_item, "is_release", is_release)
                    setattr(processed_item, "promote_release", promote_release)

                self._log_ab_metric(processed_fallback)
                return processed_fallback
            except Exception as fallback_error:
                logger.error(f"降级处理也失败: {str(fallback_error)}")
                return []
    
    def _generate_action_items(self, processed_items: list, use_agent: bool = True) -> dict:
        """生成行动清单（去重：排除已在必看内容中的新闻）"""
        try:
            # Phase 2.1: 如果启用 Agent，使用 ActionAgent 生成智能建议
            if use_agent:
                try:
                    logger.info("🤖 使用 ActionAgent 生成智能行动建议...")
                    
                    # 初始化 ActionAgent
                    tool_config = self._load_tool_config()
                    tool_executor = ToolExecutor(config=tool_config)
                    action_agent = ActionAgent(tool_executor=tool_executor)
                    
                    # 选择高优先级项目进行分析
                    high_priority_items = [
                        item for item in processed_items
                        if getattr(item, 'relevance_score', 0) >= 7
                        and getattr(item, 'actionable', False)
                    ][:10]  # 最多分析 10 条
                    
                    if high_priority_items:
                        # 生成行动建议
                        suggestions = action_agent.generate_action_suggestions(
                            high_priority_items,
                            max_suggestions=5,
                        )
                        
                        if suggestions:
                            logger.info(f"✓ ActionAgent 生成了 {len(suggestions)} 个行动建议")
                            
                            # 转换为现有格式
                            must_do = []
                            nice_to_have = []
                            
                            for suggestion in suggestions:
                                action_item = {
                                    'title': suggestion.get('title', ''),
                                    'action': suggestion.get('description', ''),
                                    'type': suggestion.get('type', 'other'),
                                    'executed': suggestion.get('executed', False),
                                    'result': suggestion.get('result', {}),
                                    'tool_call': suggestion.get('tool_call'),  # 保留工具调用信息
                                    'url': suggestion.get('result', {}).get('data', {}).get('url', ''),
                                }
                                
                                # 根据执行状态分类
                                if suggestion.get('executed'):
                                    must_do.append(action_item)
                                else:
                                    nice_to_have.append(action_item)
                            
                            return {
                                'must_do': must_do[:5],
                                'nice_to_have': nice_to_have[:5],
                                'agent_generated': True,
                            }
                except Exception as e:
                    logger.warning(f"⚠️  ActionAgent 生成失败，使用传统方法: {e}")
                    # 继续使用传统方法
            
            # 传统方法：从处理结果中提取actionable items
            filtering_prefs = self.filtering_preferences
            ignore_keywords = [
                keyword.lower() for keyword in filtering_prefs.get("ignore_keywords", [])
            ]
            minimum_optional_score = filtering_prefs.get("minimum_optional_score", 6)

            ab_variant = self.ab_variants.get("scoring_threshold_v1")
            if ab_variant == "treatment":
                minimum_optional_score = max(minimum_optional_score, 7)
            else:
                minimum_optional_score = max(minimum_optional_score, 6)

            # 🔑 关键改进：先识别出"必看内容"（personal_priority >= 8）
            must_read_urls = set()
            for item in processed_items:
                if getattr(item, 'personal_priority', 0) >= 8:  # 降低阈值从9到8
                    url = getattr(item, 'url', getattr(item, 'link', ''))
                    if url:
                        must_read_urls.add(url)
            
            logger.info(f"📌 识别到 {len(must_read_urls)} 条必看内容，将从建议行动中排除")

            must_do = []
            nice_to_have = []
            
            for item in processed_items:
                # 跳过已经在"必看内容"中的新闻
                url = getattr(item, 'url', getattr(item, 'link', ''))
                if url in must_read_urls:
                    logger.debug(f"跳过重复新闻（已在必看内容）: {getattr(item, 'title', '')}")
                    continue

                if self._is_release_candidate(item) and not self._should_promote_release(item):
                    logger.debug(f"跳过普通版本更新: {getattr(item, 'title', '')}")
                    continue
 
                title = getattr(item, 'title', '') or ""
                title_lower = title.lower()
                if any(keyword in title_lower for keyword in ignore_keywords):
                    logger.debug(f"过滤掉低价值内容: {title}")
                    continue

                if not getattr(item, 'actionable', False):
                    continue

                impact_text = getattr(item, 'impact_analysis', '') or getattr(item, 'why_matters_to_you', '') or ""

                relevance_score = getattr(item, 'relevance_score', None)
                if relevance_score is None:
                    continue

                relevance_score = int(relevance_score) if relevance_score else 0
                if relevance_score >= 8:
                    must_do.append({
                        'title': getattr(item, 'title', ''),
                        'action': impact_text,
                        'source': getattr(item, 'source', ''),
                        'url': getattr(item, 'url', getattr(item, 'link', ''))
                    })
                elif relevance_score >= minimum_optional_score:
                    nice_to_have.append({
                        'title': getattr(item, 'title', ''),
                        'action': impact_text,
                        'source': getattr(item, 'source', ''),
                        'url': getattr(item, 'url', getattr(item, 'link', ''))
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
    
    def _load_tool_config(self) -> dict:
        """加载工具配置"""
        tool_config = {}
        
        # GitHub 配置
        github_token = os.getenv("GITHUB_TOKEN")
        github_repo = os.getenv("GITHUB_DEFAULT_REPO", "")
        if github_token or github_repo:
            tool_config["github"] = {
                "token": github_token,
                "default_repo": github_repo,
            }
        
        # 日历配置
        calendar_email = os.getenv("CALENDAR_EMAIL", "")
        if calendar_email:
            tool_config["calendar"] = {
                "email": calendar_email,
            }
        
        # 阅读列表配置
        reading_list_integration = os.getenv("READING_LIST_INTEGRATION", "local")
        tool_config["reading_list"] = {
            "integration": reading_list_integration,
            "reading_list_path": str(project_root / "data" / "reading_list.json"),
        }
        
        return tool_config
    
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
            
            # 生成报告ID
            report_id = f"report_{date_str}"
            
            # 生成Markdown报告
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
            
            # 生成HTML报告（带评分功能）
            logger.info(f"🌐 生成HTML报告（带评分功能）...")
            html_path = output_path.replace('.md', '.html')
            html_report = self.report_generator.generate_html_report(
                processed_items=processed_items,
                action_items=action_items,
                leaderboard_data=leaderboard_info.get('data', []),
                leaderboard_update_time=leaderboard_info.get('update_time', ''),
                market_insights=market_insights,
                output_path=output_path,
                learning_results=learning_results or {},
                report_id=report_id,
            )
            
            # 显示统计
            logger.info(f"\n📄 报告统计:")
            logger.info(f"  - 总字数: {len(report)} 字符")
            logger.info(f"  - Markdown路径: {output_path}")
            logger.info(f"  - HTML路径: {html_path}")
            logger.info(f"  - 报告ID: {report_id}")
            logger.info(f"\n💡 提示: 打开HTML文件可以评分和追踪阅读行为")
            logger.info(f"   启动追踪服务器: python src/tracking/tracking_server.py")

            self._sync_report_to_notion(
                date_str=date_str,
                markdown_content=report,
                markdown_path=output_path,
                html_path=html_path,
            )
            
            return output_path
            
        except Exception as e:
            logger.error(f"生成报告失败: {str(e)}")
            raise

    def _sync_report_to_notion(
        self,
        date_str: str,
        markdown_content: str,
        markdown_path: str,
        html_path: str,
    ) -> None:
        """Publish the report to Notion if integration is enabled."""
        if not getattr(self, "notion_sync", None) or not self.notion_sync.is_enabled:
            logger.debug("Notion 同步未启用，跳过。")
            return

        metadata = {
            "report_date": date_str,
            "markdown_path": markdown_path,
            "html_path": html_path,
            "total_chars": str(len(markdown_content)),
        }

        title = build_notion_title(date_str)
        logger.info("🗂️ 同步报告到 Notion：%s", title)
        success = self.notion_sync.sync_report(
            title=title,
            markdown_content=markdown_content,
            metadata=metadata,
        )
        if not success:
            logger.warning("⚠️ Notion 同步未成功，已跳过。")

    def _run_learning_cycle(self, processed_items: list) -> dict:
        """运行自我学习循环"""
        try:
            logger.info("\n🧠 运行自我学习循环...")
            is_weekly = self._is_weekly_report_day()
            learning_results = self.learning_engine.run_cycle(processed_items, is_weekly=is_weekly)
            
            # Phase 2.3: 运行反馈学习
            try:
                logger.info("🔄 运行反馈闭环优化...")
                feedback_engine = FeedbackLearningEngine(
                    db=self.learning_engine.db,
                    weight_adjuster=self.report_generator.weight_adjuster if hasattr(self, 'report_generator') else None,
                )
                
                # 分析反馈模式
                feedback_patterns = feedback_engine.analyze_feedback_patterns(days=7)
                
                # 强化权重
                reinforce_result = feedback_engine.reinforce_weights(days=7)
                
                # 获取可操作性指标
                actionability_metrics = feedback_engine.get_actionability_metrics(days=7)
                
                # 添加到学习结果
                learning_results.setdefault('feedback_learning', {})
                learning_results['feedback_learning'] = {
                    'patterns': feedback_patterns,
                    'reinforcements': reinforce_result,
                    'actionability': actionability_metrics,
                }
                
                logger.info("✓ 反馈闭环优化完成")
            except Exception as e:
                logger.warning(f"⚠️  反馈学习失败: {e}")
            
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

    def _log_ab_metric(self, processed_items: list) -> None:
        if not processed_items or not getattr(self, "ab_variants", None):
            return

        try:
            engagement_score = sum(
                getattr(item, "personal_priority", 0) for item in processed_items
            ) / len(processed_items)
        except Exception:
            engagement_score = 0.0

        for exp_id, experiment in self.ab_experiments.items():
            variant = self.ab_variants.get(exp_id)
            if not variant:
                continue
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


def timeout_handler(signum, frame):
    """超时信号处理器"""
    raise TimeoutError("执行超时：主流程运行时间超过限制")


def main():
    """主函数（带超时保护）"""
    parser = argparse.ArgumentParser(description="AI Digest Report Generator")
    parser.add_argument("--days-back", type=int, default=None, help="采集最近N天的数据（默认：周一3天，其他2天）")
    parser.add_argument("--list-recommendations", action="store_true", help="列出待审批的信息源")
    parser.add_argument("--apply-recommendation", help="批准并加入配置的新信息源（输入URL或名称）")
    parser.add_argument("--reject-recommendation", help="拒绝候选信息源（输入URL或名称）")
    parser.add_argument("--learning-summary", action="store_true", help="打印学习引擎的周度摘要")
    parser.add_argument("--learning-only", action="store_true", help="仅运行学习循环，跳过周报生成")
    parser.add_argument("--use-langgraph", action="store_true", help="[已废弃] 默认已使用 LangGraph，此参数已无效果")
    parser.add_argument("--ab-summary", action="store_true", help="输出当前AB测试统计摘要")
    parser.add_argument("--timeout", type=int, default=600, help="主流程最大执行时间（秒），默认600秒（10分钟）")
    args = parser.parse_args()
    
    # 自动判断 days_back：如果未指定，则周一使用3天，其他时间使用2天
    if args.days_back is None:
        today = datetime.now()
        # weekday(): 0=周一, 1=周二, ..., 6=周日
        if today.weekday() == 0:  # 周一
            args.days_back = 3
            logger.info("📅 今天是周一，自动设置扫描过去 3 天的内容")
        else:
            args.days_back = 2
            logger.info(f"📅 今天是{['周一','周二','周三','周四','周五','周六','周日'][today.weekday()]}，自动设置扫描过去 2 天的内容")
    else:
        logger.info(f"📅 手动指定扫描过去 {args.days_back} 天的内容")
    
    # 设置主流程超时保护（仅Unix系统）
    if hasattr(signal, 'SIGALRM') and args.timeout > 0:
        signal.signal(signal.SIGALRM, timeout_handler)
        signal.alarm(args.timeout)
        logger.info(f"⏱ 已设置主流程超时保护: {args.timeout}秒")

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
            logger.warning("--use-langgraph 参数已废弃，默认 run() 方法已使用 LangGraph。")
            # 保持向后兼容，但使用统一的 run() 方法
            generator.run(days_back=args.days_back, learning_only=args.learning_only)
        else:
            # 默认使用 LangGraph 工作流
            generator.run(days_back=args.days_back, learning_only=args.learning_only)
        
        # 取消超时alarm
        if hasattr(signal, 'SIGALRM'):
            signal.alarm(0)
        
    except TimeoutError as e:
        logger.error(f"❌ {str(e)}")
        logger.error("建议：")
        logger.error("  1. 检查网络连接")
        logger.error("  2. 使用 --timeout 参数增加超时时间")
        logger.error("  3. 检查卡住的数据源（查看日志中最后处理的源）")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("\n用户中断执行")
        if hasattr(signal, 'SIGALRM'):
            signal.alarm(0)
        sys.exit(0)
    except Exception as e:
        logger.error(f"程序执行失败: {str(e)}", exc_info=True)
        if hasattr(signal, 'SIGALRM'):
            signal.alarm(0)
        sys.exit(1)


if __name__ == "__main__":
    main()

