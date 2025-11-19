"""
AI Processor
使用Claude进行内容总结、相关性打分和影响分析
通过Poe API调用Claude模型
"""

import logging
from typing import List, Dict, Optional
from dataclasses import dataclass, field
import os
import asyncio
from fastapi_poe import get_bot_response
from fastapi_poe.types import ProtocolMessage
from src.learning.explicit_feedback import ExplicitFeedbackManager, FewShotExample

logger = logging.getLogger(__name__)


@dataclass
class ProcessedItem:
    """AI处理后的条目"""
    # 原始信息
    title: str
    link: str
    source: str
    published_date: str
    original_summary: str
    
    # AI处理结果
    ai_summary: str          # 3句话总结
    relevance_score: int     # 相关性评分 (0-10)
    why_matters: str         # 为什么重要
    impact_analysis: str     # 对你的影响
    category: str            # 分类（头条/框架/模型/项目）
    headline_priority: int = 0  # 头条优先级（仅headline类别，0-10）
    
    # 元数据
    priority: int = 5
    actionable: bool = False
    project_relevance: Dict[str, int] = field(default_factory=dict)  # 各项目相关度
    personal_priority: int = 5
    why_matters_to_you: str = ""
    related_projects: List[str] = field(default_factory=list)
    deep_dive_recommended: bool = False
    deep_dive_reason: str = ""
    article_type: str = "general"


class AIProcessor:
    """AI处理器：使用Claude分析内容（通过Poe API）"""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        user_profile: Optional[Dict] = None,
        model: str = "Claude-Haiku-4.5",
        explicit_feedback_manager: Optional[ExplicitFeedbackManager] = None,
    ):
        """
        初始化AI处理器
        
        Args:
            api_key: Poe API Key
            user_profile: 用户画像配置
            model: Poe上的Claude模型名称（Claude-Haiku-4.5, Claude-Sonnet-4.5等）
        """
        api_key = api_key or os.getenv('POE_API_KEY')
        if not api_key:
            raise ValueError("必须提供POE_API_KEY环境变量")
        
        self.api_key = api_key
        self.model = model
        self.user_profile = user_profile or {}
        self.explicit_feedback_manager = explicit_feedback_manager
        
        logger.info(f"✓ AI处理器初始化完成（Poe模型：{model}）")
    
    def process_batch(self, items: List[Dict]) -> List[ProcessedItem]:
        """
        批量处理条目
        
        Args:
            items: 原始条目列表（RSS或GitHub）
            
        Returns:
            处理后的条目列表
        """
        processed = []
        
        for i, item in enumerate(items):
            try:
                processed_item = self.process_single(item)
                processed.append(processed_item)
                
                if (i + 1) % 5 == 0:
                    logger.info(f"已处理 {i + 1}/{len(items)} 条目")
                    
            except Exception as e:
                logger.error(f"处理条目失败: {str(e)}")
        
        logger.info(f"✓ AI处理完成：{len(processed)}/{len(items)} 条目")
        return processed
    
    def process_single(self, item) -> ProcessedItem:
        """
        处理单个条目
        
        Args:
            item: 原始条目（RSSItem或GitHubRelease对象）
            
        Returns:
            处理后的条目
        """
        # 提取原始数据（使用getattr处理dataclass对象）
        title = getattr(item, 'title', '')
        link = getattr(item, 'link', '')
        source = getattr(item, 'source', getattr(item, 'repo_name', ''))
        summary = getattr(item, 'summary', getattr(item, 'description', ''))
        published = getattr(item, 'published', '')
        
        # 构建用户上下文
        user_context = self._build_user_context()
        
        # 调用Claude进行分析
        analysis = self._call_claude_for_analysis(
            title=title,
            summary=summary,
            source=source,
            user_context=user_context
        )

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

        # 构建ProcessedItem
        processed = ProcessedItem(
            title=title,
            link=link,
            source=source,
            published_date=str(published) if published else "",
            original_summary=summary[:500],
            ai_summary=analysis.get('summary', ''),
            relevance_score=analysis.get('relevance_score', 5),
            why_matters=analysis.get('why_matters', ''),
            impact_analysis=analysis.get('impact_analysis', ''),
            category=analysis.get('category', 'other'),
            headline_priority=analysis.get('headline_priority', 0),
            priority=personal_priority,
            actionable=analysis.get('actionable', False),
            project_relevance=normalized_project_relevance,
            personal_priority=personal_priority,
            why_matters_to_you=why_matters_to_you,
            related_projects=related_projects,
            deep_dive_recommended=bool(analysis.get('deep_dive_recommended', False)),
            deep_dive_reason=analysis.get('deep_dive_reason', ''),
            article_type=analysis.get('article_type', 'general')
        )
        
        return processed
    
    def _build_user_context(self) -> str:
        """构建用户上下文描述"""
        if not self.user_profile:
            return """用户背景：
- 角色：Backend Developer → AI Engineer
- 经验：20+ years backend development
- 职业目标：在企业内部落地AI应用
- 活跃项目：mutation-test-killer, ai-digest, rag-practics
- 当前关注：RAG系统、AI Agent架构、AI生产力工具
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
    
    def _call_claude_for_analysis(
        self,
        title: str,
        summary: str,
        source: str,
        user_context: str
    ) -> Dict:
        """
        通过Poe API调用Claude进行分析
        
        Returns:
            包含分析结果的字典
        """
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

        few_shot_block = self._build_few_shot_block(title, summary)

        prompt = f"""你是一个AI工程师的技术助理，负责分析技术更新信息。

{user_context}{project_instruction}{few_shot_block}

请分析以下技术更新：

来源：{source}
标题：{title}
内容：{summary}

请提供以下分析（JSON格式）：

1. **summary** (3句话总结):
   - 第1句：这是什么（What）
   - 第2句：为什么重要（Why）
   - 第3句：具体变化（How）

2. **relevance_score** (0-10评分):
   - 10分：直接影响用户当前项目，必须立即关注
   - 7-9分：相关性高，建议本周了解
   - 4-6分：有价值，可以收藏稍后阅读
   - 0-3分：不相关

3. **why_matters** (1-2句话):
   解释为什么这个更新对用户重要

4. **impact_analysis** (1-2句话，可执行建议):
   具体说明对用户的影响和建议行动
   例如："立即升级到1.0.30，否则你第3个月的项目会崩溃"

5. **category** (选一个，注意来源判断):
   - headline: 头条新闻/媒体报道
     * 来自TechCrunch/VentureBeat/The Verge/MIT Tech Review/Import AI的**新闻报道**
     * 新模型发布、产品上线、融资、收购、重大宕机、行业政策
     * 公司动态、市场分析、产品评测、行业趋势报道
     * **关键**：媒体新闻报道优先归为headline，而非article
   - framework: 框架更新（LangChain/LlamaIndex等版本发布、功能更新）
   - model: 新模型/平台（仅限本地部署工具、推理优化工具，如Ollama、vLLM）
   - article: 深度技术文章/教程/最佳实践
     * **仅限**：教程、How-to指南、技术深度分析
     * **排除**：新闻报道（即使来自技术博客）
   - project: 开源项目（新发布的AI工具、库）
   - other: 其他

6. **headline_priority** (0-10，仅headline类别需要填写):
   - 10分：行业地震级事件（GPT-5发布、OpenAI被收购、Claude大规模宕机）
   - 8-9分：重大事件（重要产品发布、独角兽融资、重大技术突破）
   - 6-7分：重要新闻（产品发布、Google/Meta/Microsoft的AI动态、重要收购、市场趋势）
   - 4-5分：一般新闻（小公司融资、产品更新、行业观察）
   - 2-3分：普通资讯（常规更新、一般性报道）
  
   **媒体来源加分**：来自TechCrunch/VentureBeat/The Verge/MIT Tech Review等主流媒体的新闻，在同等重要性下+1分
   注意：只有category为headline时才需要填写此字段，其他类别填0

7. **actionable** (true/false):
   是否需要用户采取行动（如升级、测试、学习）

8. **personal_priority** (0-10):
   - 10分：直接帮助当前项目或企业AI落地，必须立即跟进
   - 7-9分：强相关，建议本周安排时间
   - 4-6分：有启发性，可加入稍后阅读清单
   - 0-3分：暂时无需关注

9. **project_relevance** (对象):
   - 键：项目名称（必须与上方列表一致）
   - 值：0-10整数分，表示该内容对项目的帮助程度

10. **why_matters_to_you** (1-2句话):
    - 明确指出这条信息如何帮助David的项目、职业目标或学习重点

11. **related_projects** (数组):
    - 列出所有评分≥6的项目名称
    - 如果没有则返回[]

12. **deep_dive_recommended** (布尔):
    - true：如果这篇内容值得安排AI研究助手做深入分析或实验
    - 满足任一条件即可：
      * personal_priority ≥ 9
      * 文章提供了可操作的技术方案/教程/代码
      * 与当前项目技术路线形成明显对比或战略冲击
    - false：否则

13. **deep_dive_reason** (字符串):
    - 如果 deep_dive_recommended 为 true，用一句话说明推荐原因
    - 例如："提供完整多Agent RAG实现，可直接用于 mutation-test-killer"
    - 如果为 false，填空字符串

14. **article_type** (字符串):
    - "trend": 行业趋势、观点或战略分析
    - "technical": 技术教程、架构拆解、含示例代码的文章
    - "general": 其他内容

附加要求：
- 如果对deep_dive_recommended的判断不确定，请给出false并在reason说明原因
- 请确保 deep_dive_reason 具体明确，避免泛泛而谈
- 如果 personal_priority < 7 且文章偏新闻报道，通常无需推荐深度研究

请ONLY返回纯JSON对象，不要添加任何解释、markdown标记或其他文字。
直接以 {{ 开始，以 }} 结束。
示例格式：
{{
  "summary": "...",
  "relevance_score": 8,
  "why_matters": "...",
  "impact_analysis": "...",
  "category": "headline",
  "headline_priority": 9,
  "actionable": true,
  "personal_priority": 9,
  "project_relevance": {{"项目A": 8, "项目B": 3}},
  "why_matters_to_you": "...",
  "related_projects": ["项目A"]
}}
"""

        try:
            # 调用Poe API（异步方法，需要在同步环境中运行）
            response_text = asyncio.run(self._call_poe_api(prompt))
            
            # 检查空响应
            if not response_text or len(response_text.strip()) == 0:
                logger.warning(f"收到空响应，标题: {title[:50]}")
                return self._get_default_analysis(title)
            
            # 强化的JSON清理逻辑
            import json
            
            # 方法1：先清理markdown代码块标记
            cleaned = response_text.strip()
            cleaned = cleaned.replace('```json\n', '').replace('```json', '')
            cleaned = cleaned.replace('\n```', '').replace('```', '')
            cleaned = cleaned.strip()
            
            # 方法2：如果还是失败，尝试提取{}之间的内容
            if not cleaned.startswith('{'):
                if '{' in cleaned and '}' in cleaned:
                    start = cleaned.find('{')
                    end = cleaned.rfind('}') + 1
                    cleaned = cleaned[start:end]
                else:
                    # 没有找到JSON，记录完整响应
                    logger.warning(f"响应中没有JSON格式内容，前100字符: {response_text[:100]}")
                    return self._get_default_analysis(title)
            
            # 解析JSON
            try:
                analysis = json.loads(cleaned)
            except json.JSONDecodeError as je:
                # 记录详细错误信息
                logger.error(f"JSON解析失败: {str(je)}")
                logger.error(f"清理后的内容前200字符: {cleaned[:200]}")
                logger.error(f"原始响应前200字符: {response_text[:200]}")
                return self._get_default_analysis(title)
            
            # 确保返回包含headline_priority字段
            if 'headline_priority' not in analysis:
                analysis['headline_priority'] = 0
            
            return analysis
            
        except Exception as e:
            logger.error(f"AI处理异常: {str(e)}")
            return self._get_default_analysis(title)
    
    def _get_default_analysis(self, title: str) -> dict:
        """
        返回默认的分析结果
        
        Args:
            title: 标题
            
        Returns:
            默认分析字典
        """
        return {
            'summary': f"{title[:100]}...",
            'relevance_score': 5,
            'why_matters': "需要进一步分析",
            'impact_analysis': "建议查看详细内容",
            'category': 'other',
            'headline_priority': 0,
            'actionable': False,
            'personal_priority': 5,
            'project_relevance': {},
            'why_matters_to_you': "需要进一步分析",
            'related_projects': [],
            'deep_dive_recommended': False,
            'deep_dive_reason': "",
            'article_type': "general"
        }
    
    async def _call_poe_api(self, prompt: str) -> str:
        """
        异步调用Poe API
        
        Args:
            prompt: 完整的prompt
            
        Returns:
            模型响应文本
        """
        message = ProtocolMessage(role="user", content=prompt)
        
        full_response = ""
        async for partial in get_bot_response(
            messages=[message],
            bot_name=self.model,
            api_key=self.api_key
        ):
            full_response += partial.text
        
        return full_response
    
    def select_top_items(
        self,
        items: List[ProcessedItem],
        top_n: int = 3
    ) -> List[ProcessedItem]:
        """
        选择Top N条目（基于相关性评分）
        
        Args:
            items: 处理后的条目列表
            top_n: 返回数量
            
        Returns:
            Top N条目
        """
        sorted_items = sorted(items, key=lambda x: x.relevance_score, reverse=True)
        return sorted_items[:top_n]
    
    def categorize_items(self, items: List[ProcessedItem]) -> Dict[str, List[ProcessedItem]]:
        """
        按类别分组
        
        Args:
            items: 处理后的条目列表
            
        Returns:
            按类别分组的字典
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
            category = item.category
            if category in categorized:
                categorized[category].append(item)
            else:
                categorized['other'].append(item)
        
        return categorized
    
    def generate_action_items(
        self,
        items: List[ProcessedItem]
    ) -> Dict[str, List[str]]:
        """
        生成行动清单
        
        Args:
            items: 处理后的条目列表
            
        Returns:
            包含必做和可选任务的字典
        """
        must_do = []
        nice_to_have = []
        
        for item in items:
            if item.actionable:
                if item.relevance_score >= 9:
                    must_do.append(item.impact_analysis)
                elif item.relevance_score >= 7:
                    nice_to_have.append(f"了解 {item.title}")
        
        return {
            'must_do': must_do[:3],  # 最多3个必做
            'nice_to_have': nice_to_have[:5]  # 最多5个可选
        }

    def _build_few_shot_block(self, title: str, summary: str) -> str:
        if not self.explicit_feedback_manager:
            return ""

        article_text = "\n".join(part for part in [title, summary] if part).strip()
        if not article_text:
            return ""

        return self.explicit_feedback_manager.build_prompt_block(
            article_text,
            correction_type="analysis",
            fallback_type="analysis",
            max_examples=3,
        )

