"""
AI批量处理器 - 一次性筛选和分析所有新闻
性能优化版：1次API调用代替158次
"""

import asyncio
import json
import logging
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field

try:
    from json_repair import repair_json
except ImportError:  # pragma: no cover
    repair_json = None

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
        
        选项2: 为论文类别单独处理，确保至少处理一部分论文
        
        Args:
            all_items: 所有采集的条目
            top_n: 筛选出的数量
            
        Returns:
            处理后的条目列表
        """
        logger.info(f"🚀 批量处理模式启动: {len(all_items)} 条新闻 → 筛选 Top {top_n}")
        
        # 选项2: 分离论文和新闻，确保论文被优先处理
        paper_items = []
        news_items = []
        for item in all_items:
            category = getattr(item, 'category', item.get('category', '') if hasattr(item, 'get') else '')
            if category == 'paper':
                paper_items.append(item)
            else:
                news_items.append(item)
        
        logger.info(f"📄 论文: {len(paper_items)} 条, 📰 新闻: {len(news_items)} 条")
        
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
        
        # 确保至少处理15篇论文（如果有的话）
        paper_quota = min(15, len(paper_items))
        news_quota = top_n - paper_quota
        
        # 重新组合：论文优先（已按来源优先级排序）
        prioritized_items = paper_items[:paper_quota] + news_items[:news_quota]
        
        # 统计论文来源
        paper_sources = {}
        for p in paper_items[:paper_quota]:
            source = getattr(p, 'source', 'Unknown')
            paper_sources[source] = paper_sources.get(source, 0) + 1
        
        logger.info(f"✓ 优先处理: {len(paper_items[:paper_quota])} 篇论文 + {len(news_items[:news_quota])} 条新闻")
        if paper_sources:
            logger.info(f"  论文来源: {', '.join([f'{k}: {v}' for k, v in sorted(paper_sources.items(), key=lambda x: x[1], reverse=True)])}")
        
        # 构建新闻列表（简化版，只发送标题和摘要）
        news_list = []
        for i, item in enumerate(prioritized_items, 1):
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

⚠️ 数据一致性要求（必须严格遵守）：
1. "index" 必须准确对应原始条目序号
2. "summary" 必须总结该 index 对应条目的实际内容
3. 绝对不能把第N条的内容总结成第M条的summary
4. 如果不确定某条内容，请如实反映原始信息

⚠️ Hacker News 内容处理特别要求：
- 如果原始摘要只有"热门讨论：X分，Y条评论"，请基于标题推断内容主题
- 生成一个有意义的中文摘要，说明这个讨论可能涉及的内容和价值
- 例如：标题"Three kinds of AI products work" → 摘要"讨论了三种成功的AI产品模式，分析了什么样的AI产品能够真正为用户创造价值并获得市场成功"

⚠️ 语言要求：
- 所有摘要必须使用中文
- 即使原文是英文，也要翻译成中文
- 保持专业术语的准确性（如RAG、LLM等可保留英文缩写）

{user_context}{project_instruction}{few_shot_block}

请筛选最重要的{top_n}条并详细分析。

所有新闻：
{''.join(news_list)}

返回JSON数组，每条新闻包含：
[
  {{
    "index": 编号(1-{len(all_items)}),
    "summary": "用中文写3句话总结该index对应条目的实际内容：第1句是什么(What)、第2句为什么重要(Why)、第3句具体变化(How)。对于Hacker News讨论，请基于标题推断并生成有意义的中文摘要，不要只写'热门讨论'。所有英文内容必须翻译成中文",
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
1. category="paper": 学术论文/研究成果
   - **所有来自arXiv（cs.CL/cs.IR/cs.LG/cs.AI/stat.ML）的论文**
   - **所有来自Hugging Face Papers的论文**
   - 学术研究、技术报告、预印本
   - **优先级最高**：论文类内容必须保留，用于"论文精选"板块

2. category="headline": 头条新闻/媒体报道
   - **来自TechCrunch/VentureBeat/The Verge/MIT Tech Review/Import AI的新闻报道**
   - 新模型发布、产品上线、融资、收购、重大宕机、行业政策
   - 公司动态、市场分析、产品评测、行业趋势报道
   - Hacker News的热门讨论（但不包括框架更新）
   - **严格排除**：
     * Towards Data Science的文章（必须归为article）
     * GitHub Release（必须归为framework或model）
     * 框架版本更新（必须归为framework）
     * arXiv论文（必须归为paper）

3. category="framework": 框架/SDK更新
   - **所有GitHub Release的框架更新**：LangChain/LlamaIndex/LangGraph/OpenAI Python SDK等
   - 版本号标题（如v1.0.3, langchain-core==1.0.2）必须归为framework

4. category="article": 深度技术文章/教程/最佳实践
   - **所有来自Towards Data Science的文章**（无论标题是什么）
   - 教程、How-to指南、技术深度分析
   - **排除**：新闻报道、学术论文

5. category="model": 新模型/推理工具更新
   - **Ollama/vLLM的GitHub Release**（如v0.12.7）
   - 新模型发布（但媒体报道除外）

6. category="project": 开源项目（新发布的AI工具、库）
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
7. **特别关注Fintech相关内容**（必须优先保留）：
   - 来自Fintech Times、Finextra、TechCrunch Fintech、Fintech News等源的内容应给予较高relevance_score（≥6分）
   - 涉及金融科技企业AI落地实践的内容（Vanguard、BlackRock、JPMorgan、Capital One、Goldman Sachs、Stripe、PayPal等）
   - VC投资的AI+Fintech初创公司相关内容（Y Combinator、a16z、Sequoia等）
   - Fintech相关的AI应用：SDLC、客户服务、风险管理、数据分析、业务流程自动化
   - 在筛选Top {top_n}条时，应确保包含至少5-10条Fintech相关内容（如果存在）

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
            try:
                analyses = json.loads(cleaned)
            except json.JSONDecodeError as e:
                logger.warning(f"首次解析失败，尝试自动修复JSON: {str(e)}")
                repaired = self._repair_json_string(cleaned)
                analyses = json.loads(repaired)
            
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
                    
                    # 获取原始 summary，用于数据一致性验证
                    original_summary = getattr(original, 'summary', None)
                    if original_summary is None and hasattr(original, 'get'):
                        original_summary = original.get('summary', '')
                    original_summary = original_summary or ''

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
                    
                    # 数据一致性验证：检查 AI 返回的 summary 是否与原始内容匹配
                    ai_summary = analysis.get('summary', '')
                    why_matters = analysis.get('why_matters', '')
                    
                    # 如果 AI 返回的 summary 与原始 title/url 明显不匹配，使用原始 summary
                    # 检测关键词不匹配（例如：title 说 Anthropic，但 summary 说 vector database）
                    title_lower = title.lower()
                    ai_summary_lower = ai_summary.lower()
                    
                    # 提取 title 中的关键词（去除常见词和技术后缀）
                    stop_words = {'the', 'and', 'for', 'with', 'from', 'that', 'this', 'what', 'when', 'where', 
                                 'how', 'why', 'are', 'was', 'were', 'been', 'have', 'has', 'had', 'will', 'would',
                                 'via', 'using', 'based', 'system', 'model', 'learning', 'paper'}
                    title_keywords = set([w for w in title_lower.split() if len(w) > 4 and w not in stop_words])
                    
                    # 检查是否有任何关键词出现在 summary 中
                    # 对于中文摘要，我们更宽松一些，只要有1-2个关键词匹配即可
                    keyword_matches = sum(1 for keyword in title_keywords if keyword in ai_summary_lower)
                    
                    # 判断是否为严重不匹配：
                    # 1. 有多个关键词（≥3个）
                    # 2. 但一个都不匹配
                    # 3. 且原始 summary 存在且不是占位符
                    is_serious_mismatch = (
                        len(title_keywords) >= 3 and 
                        keyword_matches == 0 and 
                        original_summary and 
                        len(original_summary) > 20 and
                        'Author/Org:' not in original_summary  # 排除占位符式的原始摘要
                    )
                    
                    if is_serious_mismatch:
                        logger.warning(f"⚠️  数据不一致！Title: '{title[:50]}...' 但 AI summary 不匹配，使用原始 summary")
                        final_summary = original_summary
                        # 重置 why_matters 和相关字段，避免错误信息传播
                        why_matters = f"来自 {source} 的内容"
                        why_matters_to_you = f"来自 {source} 的内容，需要进一步分析"
                    else:
                        # 使用 AI 生成的摘要（可能是中文）
                        final_summary = ai_summary if ai_summary else original_summary
                    
                    processed.append(ProcessedItem(
                        source=source,
                        title=title,
                        url=url,
                        published_date=pub_date,
                        summary=final_summary,
                        relevance_score=analysis.get('relevance_score', 5),
                        category=analysis.get('category', 'other'),
                        why_matters=why_matters,
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
        
        # 将中文引号/省略号替换为标准字符
        replacements = {
            "“": '"',
            "”": '"',
            "’": "'",
            "‘": "'",
            "…": "...",
        }
        for src, target in replacements.items():
            cleaned = cleaned.replace(src, target)
        
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
        
        # 去除末尾多余的逗号（例如 [...,] 或 {...,}）
        cleaned = re.sub(r',\s*(\]}|\})', r'\1', cleaned)
        return cleaned
    
    def _repair_json_string(self, text: str) -> str:
        """
        尝试修复JSON字符串中的常见格式问题（例如未转义的引号）
        """
        if not text:
            return text
        
        if repair_json is not None:
            try:
                return repair_json(text)
            except Exception as err:  # pragma: no cover - 仅日志警告
                logger.warning(f'json_repair 解析失败: {err}')
        
        result = []
        in_string = False
        escape = False
        length = len(text)
        
        i = 0
        while i < length:
            ch = text[i]
            
            if in_string:
                if escape:
                    result.append(ch)
                    escape = False
                elif ch == '\\':
                    escape = True
                    result.append(ch)
                elif ch == '"':
                    # 查看后续字符，判断是否为真正的字符串结束
                    j = i + 1
                    while j < length and text[j] in ' \t\r\n':
                        j += 1
                    next_char = text[j] if j < length else ''
                    if next_char in {',', '}', ']'}:
                        result.append(ch)
                        in_string = False
                    else:
                        # 认为是未转义的引号，自动转义
                        result.append('\\')
                        result.append('"')
                elif ch == '\n':
                    result.append('\\n')
                elif ch == '\r':
                    # 忽略\r，已由\n处理
                    pass
                else:
                    result.append(ch)
            else:
                if ch == '"':
                    in_string = True
                result.append(ch)
            i += 1
        
        # 如果字符串未正常结束，补齐引号
        if in_string:
            result.append('"')
        
        repaired = ''.join(result)
        # 再次去掉尾部多余逗号
        repaired = re.sub(r',\s*(\]}|\})', r'\1', repaired)
        return repaired
    
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

        sample_context = "\n".join(news_list[:5])
        return self.explicit_feedback_manager.build_prompt_block(
            sample_context,
            correction_type="batch_selection",
            fallback_type="analysis",
            max_examples=3,
        )

