"""
Report Generator
报告生成器：使用Jinja2模板生成Markdown周报
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional
from pathlib import Path
from jinja2 import Environment, FileSystemLoader
import os

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
        
        self.template_dir = template_dir
        self.version = version
        self.headline_source_limit = max(1, headline_source_limit)
        
        # 初始化Jinja2环境
        self.env = Environment(
            loader=FileSystemLoader(template_dir),
            trim_blocks=True,
            lstrip_blocks=True
        )
        
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
        
        # 选择头条列表（默认10条，优先行业大事）
        top_headlines = self._select_top_headlines(processed_items, top_count=10)
        
        # 个性化关注：必读与附录候选
        sorted_by_priority = sorted(
            processed_items,
            key=lambda x: getattr(x, 'personal_priority', getattr(x, 'relevance_score', 0)),
            reverse=True
        )

        must_read_items = [
            item for item in sorted_by_priority
            if getattr(item, 'personal_priority', 0) >= 8  # 降低阈值从9到8
        ][:5]

        selected_titles = {item.title for item in top_headlines}
        selected_titles.update(item.title for item in must_read_items)

        appendix_items = [
            item for item in sorted_by_priority
            if 6 <= getattr(item, 'personal_priority', 0) <= 8
            and item.title not in selected_titles
        ][:15]

        selected_titles.update(item.title for item in appendix_items)
        
        # 准备模板数据
        paper_radar = self._build_paper_radar(processed_items)

        template_data = {
            'report_date': datetime.now().strftime('%Y年%m月%d日'),
            'generation_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'version': self.version,
            'top_headlines': top_headlines,
            'action_items': action_items,
            'must_read_items': must_read_items,
            'appendix_items': appendix_items,
            'leaderboard_data': leaderboard_data if leaderboard_data else [],
            'leaderboard_update_time': leaderboard_update_time,
            'market_insights': market_insights if market_insights else [],
            'framework_items': [item for item in categorized.get('framework', []) if item.title not in selected_titles][:5],
            'model_items': [item for item in categorized.get('model', []) if item.title not in selected_titles][:5],
            'article_items': [item for item in categorized.get('article', []) if item.title not in selected_titles][:3],
            'project_items': [item for item in categorized.get('project', []) if item.title not in selected_titles][:3],
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
    
    def _select_top_headlines(self, processed_items: List, top_count: int = 10) -> List:
        """
        选择头条列表，优先行业大事
        
        策略：
        1. headline类别优先，按headline_priority排序
        2. 如果headline不足 top_count 条，补充高分article/project（排除framework/model）
        3. 去重：避免同一来源的多个条目
        
        Args:
            processed_items: 处理后的条目列表
            top_count: 需要选择的头条数量
            
        Returns:
            头条条目列表
        """
        # 第一步：收集所有headline类别的条目
        # 强制排除：Towards Data Science必须归为article
        headlines = [
            item for item in processed_items 
            if item.category == 'headline'
            and 'Towards Data Science' not in item.source  # 强制排除TDS
        ]
        headlines.sort(key=lambda x: getattr(x, 'headline_priority', 0), reverse=True)
        
        # 去重：同一来源只取第一条（避免LangChain 1.0.1和1.0.2同时出现）
        seen_sources: Dict[str, int] = {}
        unique_headlines = []
        
        for item in headlines:
            # 提取来源的核心名称（去掉版本号、括号内容等）
            source_key = item.source.split()[0].split('(')[0]  # "LangChain" from "LangChain (v1.0.2)"

            if seen_sources.get(source_key, 0) >= self.headline_source_limit:
                continue

            unique_headlines.append(item)
            seen_sources[source_key] = seen_sources.get(source_key, 0) + 1
            if len(unique_headlines) >= top_count:
                break
        
        # 第二步：如果headline不足目标数量，补充其他高质量内容（排除framework/model/TDS）
        if len(unique_headlines) < top_count:
            others = [
                item for item in processed_items 
                if item.category in ['article', 'project']  # 只要article和project，排除framework和model
                and item.relevance_score >= 7
                and 'Towards Data Science' not in item.source  # 强制排除TDS
            ]
            others.sort(key=lambda x: x.relevance_score, reverse=True)
            
            for item in others:
                if len(unique_headlines) >= top_count:
                    break
                
                source_key = item.source.split()[0].split('(')[0]
                if seen_sources.get(source_key, 0) >= self.headline_source_limit:
                    continue
                unique_headlines.append(item)
                seen_sources[source_key] = seen_sources.get(source_key, 0) + 1
                if len(unique_headlines) >= top_count:
                    break
        
        # 第三步：如果仍不足目标数量，补充其他内容（严格排除framework/model/TDS）
        if len(unique_headlines) < top_count:
            remaining = [
                item for item in processed_items 
                if item not in unique_headlines
                and item.category not in ['framework', 'model']  # 明确排除framework和model，保持Top 5的"大事"属性
                and 'Towards Data Science' not in item.source  # 强制排除TDS
            ]
            remaining.sort(key=lambda x: x.relevance_score, reverse=True)
            unique_headlines.extend(remaining[:top_count - len(unique_headlines)])
        
        # 记录详细筛选信息
        category_dist = {}
        for item in unique_headlines:
            category_dist[item.category] = category_dist.get(item.category, 0) + 1
        
        logger.info(f"✓ Top {top_count}筛选完成: {len(unique_headlines)}条")
        logger.info(f"  分类分布: {category_dist}")
        
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

    def _build_paper_radar(self, processed_items: List) -> List[Dict[str, Any]]:
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

            radar_candidates.append({
                'title': getattr(item, 'title', '未命名论文'),
                'url': getattr(item, 'url', ''),
                'source': source,
                'summary': summary.strip(),
                'personal_note': personal_note.strip(),
                'published_date': self._format_date(getattr(item, 'published_date', '')),
                'personal_priority': getattr(item, 'personal_priority', getattr(item, 'relevance_score', 0)) or 0,
            })

        radar_candidates.sort(key=lambda x: x['personal_priority'], reverse=True)
        return radar_candidates[:3]

    @staticmethod
    def _format_date(date_obj: Any) -> str:
        if isinstance(date_obj, datetime):
            return date_obj.strftime('%Y-%m-%d')
        if isinstance(date_obj, str):
            return date_obj[:10]
        return ''

