"""
AI批量处理器 - 一次性筛选和分析所有新闻
性能优化版：1次API调用代替158次
"""

import asyncio
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field

from fastapi_poe import get_bot_response

from src.learning.explicit_feedback import ExplicitFeedbackManager, FewShotExample

logger = logging.getLogger(__name__)


@dataclass
class ProcessedItem:
    """处理后的条目"""
    source: str
    title: str
    url: str
    published_date: datetime
    summary: str
    relevance_score: int
    category: str
    why_matters: str
    impact_analysis: str
    headline_priority: int = 0
    actionable: bool = False
    personal_priority: int = 5
    project_relevance: Dict[str, int] = field(default_factory=dict)
    why_matters_to_you: str = ""
    related_projects: List[str] = field(default_factory=list)
    priority: int = 5
    deep_dive_recommended: bool = False
    deep_dive_reason: str = ""
    article_type: str = "general"


class AIProcessorBatch:
    """批量AI处理器"""
    
    def __init__(
        self,
        api_key: str = None,
        model_name: str = "Claude-Sonnet-4.5",
        user_profile: Dict = None,
        explicit_feedback_manager: Optional[ExplicitFeedbackManager] = None,
    ):
        """
        初始化批量处理器
        
        Args:
            api_key: Poe API密钥
            model_name: 模型名称
            user_profile: 用户配置
        """
        import os
        self.api_key = api_key or os.getenv('POE_API_KEY')
        self.model_name = model_name
        self.user_profile = user_profile or {}
        self.explicit_feedback_manager = explicit_feedback_manager
        
        if not self.api_key:
            raise ValueError("需要设置POE_API_KEY环境变量")
    
    def batch_select_and_analyze(
        self, 
        all_items: List[Dict], 
        top_n: int = 25
    ) -> List[ProcessedItem]:
        """
        一次性筛选和分析所有条目
        
        Args:
            all_items: 所有采集的条目
            top_n: 筛选出的数量
            
        Returns:
            处理后的条目列表
        """
        logger.info(f"🚀 批量处理模式启动: {len(all_items)} 条新闻 → 筛选 Top {top_n}")
        
        # 构建新闻列表（简化版，只发送标题和摘要）
        news_list = []
        for i, item in enumerate(all_items, 1):
            # 兼容dataclass和dict，智能提取来源
            source = getattr(item, 'source', item.get('source', '') if hasattr(item, 'get') else '')
            
            # 如果source为空，尝试从repo_name或其他字段提取
            if not source or source == 'Unknown':
                # GitHub Release通常有repo_name
                repo_name = getattr(item, 'repo_name', item.get('repo_name', '') if hasattr(item, 'get') else '')
                if repo_name:
                    source = repo_name
                else:
                    source = 'Unknown'
            
            title = getattr(item, 'title', item.get('title', '') if hasattr(item, 'get') else '')[:200]
            
            # 优先使用summary，没有则用description
            if hasattr(item, 'summary'):
                summary = getattr(item, 'summary', '')
            elif hasattr(item, 'description'):
                summary = getattr(item, 'description', '')
            elif hasattr(item, 'get'):
                summary = item.get('summary', item.get('description', ''))
            else:
                summary = ''
            summary = summary[:400]
            
            # 发布日期
            pub_date = getattr(item, 'published_date', item.get('published_date', '') if hasattr(item, 'get') else '')
            if isinstance(pub_date, datetime):
                pub_date = pub_date.strftime('%Y-%m-%d')
            
            news_list.append(f"{i}. [{source}] {title}\n   {summary}\n   发布: {pub_date}\n")
        
        # 构建prompt
        user_context = self._build_user_context()
        active_projects = self.user_profile.get('active_projects', [])
        project_names = [proj.get('name') for proj in active_projects if proj.get('name')]
        project_instruction = ""
        if project_names:
            bullet_lines = "\n".join([f"  - {name}" for name in project_names])
            project_instruction = (
                "\n项目相关性要求：\n"
                "- 针对以下项目分别给出0-10的整数评分（0=无关，10=需要立即采取行动）：\n"
                f"{bullet_lines}\n"
                "- JSON字段`project_relevance`必须包含上述每个项目名称作为键。\n"
            )

        few_shot_block = self._build_few_shot_block(news_list)

        prompt = f"""你是AI工程师的技术助理。我采集了{len(all_items)}条AI相关新闻。

{user_context}{project_instruction}{few_shot_block}

请筛选最重要的{top_n}条并详细分析。

所有新闻：
{''.join(news_list)}

返回JSON数组，每条新闻包含：
[
  {{
    "index": 编号(1-{len(all_items)}),
    "summary": "3句话总结：第1句是什么(What)、第2句为什么重要(Why)、第3句具体变化(How)",
    "category": "headline|framework|article|model|project",
    "headline_priority": 0-10,
    "relevance_score": 0-10,
    "why_matters": "为什么这个更新对用户重要",
    "impact_analysis": "具体影响和建议行动",
    "actionable": true|false,
    "personal_priority": 0-10,
    "project_relevance": {{"项目名称": 0-10}},
    "why_matters_to_you": "直接说明对David的价值",
    "related_projects": ["与内容高度相关的项目名称，评分≥6"],
    "deep_dive_recommended": true|false,
    "deep_dive_reason": "如果建议深入研究，用1句话说明原因；否则留空",
    "article_type": "trend|technical|general"
  }}
]

分类规则（严格遵守）：
1. category="headline": 头条新闻/媒体报道
   - **来自TechCrunch/VentureBeat/The Verge/MIT Tech Review/Import AI的新闻报道**
   - 新模型发布、产品上线、融资、收购、重大宕机、行业政策
   - 公司动态、市场分析、产品评测、行业趋势报道
   - Hacker News的热门讨论（但不包括框架更新）
   - **严格排除**：
     * Towards Data Science的文章（必须归为article）
     * GitHub Release（必须归为framework或model）
     * 框架版本更新（必须归为framework）

2. category="framework": 框架/SDK更新
   - **所有GitHub Release的框架更新**：LangChain/LlamaIndex/LangGraph/OpenAI Python SDK等
   - 版本号标题（如v1.0.3, langchain-core==1.0.2）必须归为framework

3. category="article": 深度技术文章/教程/最佳实践
   - **所有来自Towards Data Science的文章**（无论标题是什么）
   - 教程、How-to指南、技术深度分析
   - **排除**：新闻报道

4. category="model": 新模型/推理工具更新
   - **Ollama/vLLM的GitHub Release**（如v0.12.7）
   - 新模型发布（但媒体报道除外）

5. category="project": 开源项目（新发布的AI工具、库）
   - Hacker News的"Show HN"项目展示

headline_priority评分（仅headline类别）：
- 10分：行业地震级（GPT-5发布、OpenAI被收购）
- 8-9分：重大事件（重要产品发布、独角兽融资、技术突破）
- 6-7分：重要新闻（产品发布、大厂AI动态、重要收购、市场趋势）
- 4-5分：一般新闻（小公司融资、产品更新、行业观察）
- 2-3分：普通资讯

**媒体来源加分**：来自TechCrunch/VentureBeat/The Verge/MIT Tech Review的新闻+1分

筛选策略（非常重要）：
1. **优先选择headline类别**（媒体新闻、重大事件、产品发布）
2. **严格排除framework/model类别**：GitHub Release、框架更新不要进入Top 25的headline部分
3. **严格排除Towards Data Science**：所有Towards Data Science文章必须归为article，不进headline
4. 平衡不同来源（避免全是Hacker News）
5. 同一来源的多个版本更新只保留最新/最重要的
6. 确保至少有3-5条来自TechCrunch/VentureBeat/The Verge/MIT Tech Review的媒体新闻

个人优先级与项目相关性评分指南：
- personal_priority 10：直接推进企业AI落地或当前活跃项目，必须立即执行
- personal_priority 7-9：显著帮助David的学习重点或项目决策，建议本周跟进
- personal_priority 4-6：有启发性，适合记录待查
- personal_priority 0-3：短期内价值较低
- project_relevance：针对每个项目给出0-10分，10表示立刻可应用，7-9表示本周可评估，4-6表示中长期启发，0-3表示无关

深度研究推荐规则：
- 如果内容提供可直接执行的技术方案、实验步骤或代码，请设置 deep_dive_recommended = true，并给出明确理由
- 如果个人优先级 >= 9 或对任一活跃项目影响评分 >= 8，也应推荐 deep dive
- 关注能形成策略对比或冲击现有路线的新闻（例如：托管RAG vs 自建RAG）

article_type 分类：
- trend：行业趋势、观点解读、战略分析
- technical：技术实现、架构拆解、含示例代码的教程
- general：其他内容

只返回JSON数组，不要markdown标记，不要解释。
"""
        
        try:
            # 调用LLM
            logger.info("正在调用LLM进行批量分析...")
            response_text = asyncio.run(self._call_poe_api(prompt))
            
            # 解析JSON
            logger.info("解析LLM响应...")
            cleaned = self._clean_json_response(response_text)
            analyses = json.loads(cleaned)
            
            logger.info(f"✓ LLM返回 {len(analyses)} 条分析结果")
            
            # 转换为ProcessedItem
            processed = []
            for analysis in analyses:
                idx = analysis.get('index', 0) - 1
                if 0 <= idx < len(all_items):
                    original = all_items[idx]
                    
                    # 兼容dataclass和dict，智能提取来源
                    source = getattr(original, 'source', original.get('source', '') if hasattr(original, 'get') else '')
                    
                    # 如果source为空，尝试从repo_name提取
                    if not source or source == 'Unknown':
                        repo_name = getattr(original, 'repo_name', original.get('repo_name', '') if hasattr(original, 'get') else '')
                        if repo_name:
                            source = repo_name
                        else:
                            source = 'Unknown'
                    
                    title = getattr(original, 'title', original.get('title', '') if hasattr(original, 'get') else '')
                    url = getattr(original, 'url', None) or getattr(original, 'link', None)
                    if url is None and hasattr(original, 'get'):
                        url = original.get('url', original.get('link', ''))
                    url = url or ''
                    
                    pub_date = getattr(original, 'published_date', None)
                    if pub_date is None and hasattr(original, 'get'):
                        pub_date = original.get('published_date', datetime.now())
                    pub_date = pub_date or datetime.now()

                    project_relevance = analysis.get('project_relevance', {}) or {}
                    if not isinstance(project_relevance, dict):
                        project_relevance = {}
                    normalized_project_relevance = {}
                    for name, score in project_relevance.items():
                        try:
                            int_score = int(float(score))
                        except (TypeError, ValueError):
                            continue
                        normalized_project_relevance[str(name)] = max(0, min(10, int_score))

                    related_projects = analysis.get('related_projects', []) or []
                    if not isinstance(related_projects, list):
                        related_projects = []
                    if not related_projects and normalized_project_relevance:
                        related_projects = [
                            project_name
                            for project_name, score in normalized_project_relevance.items()
                            if isinstance(score, int) and score >= 6
                        ]

                    personal_priority = analysis.get('personal_priority', analysis.get('relevance_score', 5))
                    try:
                        personal_priority = int(float(personal_priority))
                    except (TypeError, ValueError):
                        personal_priority = 5
                    personal_priority = max(0, min(10, personal_priority))

                    why_matters_to_you = analysis.get('why_matters_to_you') or analysis.get('why_matters', '')
                    
                    processed.append(ProcessedItem(
                        source=source,
                        title=title,
                        url=url,
                        published_date=pub_date,
                        summary=analysis.get('summary', ''),
                        relevance_score=analysis.get('relevance_score', 5),
                        category=analysis.get('category', 'other'),
                        why_matters=analysis.get('why_matters', ''),
                        impact_analysis=analysis.get('impact_analysis', ''),
                        headline_priority=analysis.get('headline_priority', 0),
                        actionable=analysis.get('actionable', False),
                        personal_priority=personal_priority,
                        project_relevance=normalized_project_relevance,
                        why_matters_to_you=why_matters_to_you,
                        related_projects=related_projects,
                        priority=personal_priority,
                        deep_dive_recommended=bool(analysis.get('deep_dive_recommended', False)),
                        deep_dive_reason=analysis.get('deep_dive_reason', ''),
                        article_type=analysis.get('article_type', 'general')
                    ))
                else:
                    logger.warning(f"索引超出范围: {idx+1}")
            
            # 统计分类分布
            category_dist = {}
            for item in processed:
                category_dist[item.category] = category_dist.get(item.category, 0) + 1
            
            logger.info(f"✓ 批量处理完成！筛选出 {len(processed)} 条")
            logger.info(f"  分类分布: {category_dist}")
            
            return processed
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON解析失败: {str(e)}")
            logger.error(f"响应前500字符: {response_text[:500] if response_text else 'None'}")
            raise
        except Exception as e:
            logger.error(f"批量处理失败: {str(e)}")
            raise
    
    async def _call_poe_api(self, prompt: str) -> str:
        """
        调用Poe API
        
        Args:
            prompt: 提示词
            
        Returns:
            API响应文本
        """
        try:
            full_response = ""
            async for partial in get_bot_response(
                messages=[{"role": "user", "content": prompt}],
                bot_name=self.model_name,
                api_key=self.api_key
            ):
                full_response += partial.text
            
            return full_response
            
        except Exception as e:
            logger.error(f"Poe API调用失败: {str(e)}")
            raise
    
    def _clean_json_response(self, response_text: str) -> str:
        """
        清理JSON响应
        
        Args:
            response_text: 原始响应
            
        Returns:
            清理后的JSON字符串
        """
        if not response_text:
            raise ValueError("响应为空")
        
        # 去除空白
        cleaned = response_text.strip()
        
        # 去除markdown代码块标记
        cleaned = cleaned.replace('```json\n', '').replace('```json', '')
        cleaned = cleaned.replace('\n```', '').replace('```', '')
        cleaned = cleaned.strip()
        
        # 如果不是以[或{开头，尝试提取JSON
        if not cleaned.startswith('[') and not cleaned.startswith('{'):
            # 查找第一个[或{
            start_bracket = cleaned.find('[')
            start_brace = cleaned.find('{')
            
            start = -1
            if start_bracket != -1 and start_brace != -1:
                start = min(start_bracket, start_brace)
            elif start_bracket != -1:
                start = start_bracket
            elif start_brace != -1:
                start = start_brace
            
            if start != -1:
                # 查找对应的结束符
                if cleaned[start] == '[':
                    end = cleaned.rfind(']') + 1
                else:
                    end = cleaned.rfind('}') + 1
                
                if end > start:
                    cleaned = cleaned[start:end]
        
        return cleaned
    
    def _build_user_context(self) -> str:
        """构建用户上下文描述"""
        if not self.user_profile:
            return """用户背景：
- 角色：Backend Developer → AI Engineer
- 经验：20+ years backend development
- 职业目标：在企业内部落地AI应用
- 活跃项目：mutation-test-killer, ai-digest, rag-practics
"""
        
        user_info = self.user_profile.get('user_info', {})
        career_goals = self.user_profile.get('career_goals', {})
        active_projects = self.user_profile.get('active_projects', [])
        learning_focus = self.user_profile.get('learning_focus', {})
        relevance_criteria = self.user_profile.get('relevance_criteria', {})
        secondary_goals = career_goals.get('secondary', [])
        project_lines = []
        for idx, project in enumerate(active_projects, start=1):
            name = project.get('name', f"项目{idx}")
            description = project.get('description', '')
            goals = ", ".join(project.get('goals', []))
            tech_stack = ", ".join(project.get('tech_stack', []))
            lines = [f"{idx}. {name}：{description}"]
            if goals:
                lines.append(f"   目标：{goals}")
            if tech_stack:
                lines.append(f"   技术栈：{tech_stack}")
            project_lines.append("\n".join(lines))
        projects_block = "\n".join(project_lines) if project_lines else "暂无明确项目"
        current_focus = ", ".join(learning_focus.get('current', [])) or "持续探索"
        interested_focus = ", ".join(learning_focus.get('interested_in', [])) or "持续补充"
        high_priority = ", ".join(relevance_criteria.get('high_priority', []))
        medium_priority = ", ".join(relevance_criteria.get('medium_priority', []))
        low_priority = ", ".join(relevance_criteria.get('low_priority', []))
        context = f"""用户背景：
- 姓名：{user_info.get('name', '用户')}
- 角色：{user_info.get('role', 'Backend Developer → AI Engineer')}
- 经验：{user_info.get('experience', '20+ years backend development')}
- 当前阶段：{user_info.get('current_stage', 'AI学习与落地探索')}
- 职业目标（primary）：{career_goals.get('primary', '在企业内部落地AI应用')}
- 职业目标（secondary）：{', '.join(secondary_goals) if secondary_goals else '持续扩展AI能力'}

活跃项目：
{projects_block}

学习重点：
- 当前关注：{current_focus}
- 感兴趣方向：{interested_focus}

高优先级主题：{high_priority}
中优先级主题：{medium_priority}
低优先级主题：{low_priority}
"""
        return context

    def _build_few_shot_block(self, news_list: List[str]) -> str:
        if not self.explicit_feedback_manager:
            return ""

        sample_context = "\n".join(news_list[:3])
        examples = self.explicit_feedback_manager.retrieve_similar_corrections(
            sample_context,
            correction_type="batch_selection",
            top_k=2,
        )
        if not examples:
            examples = self.explicit_feedback_manager.get_recent_corrections(
                correction_type="analysis",
                top_k=2,
            )
        if not examples:
            return ""

        lines = ["\n参考用户修正示例（请避免重复错误）："]
        for idx, example in enumerate(examples, start=1):
            lines.append(f"{idx}. 错误输出：{example.original_output}")
            lines.append(f"   正确输出：{example.corrected_output}")
        lines.append("")
        return "\n".join(lines)

