"""Extract preference facts from high-priority items using Poe."""

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict, Iterable, List, Optional

from fastapi_poe import get_bot_response
from fastapi_poe.types import ProtocolMessage


class FactExtractor:
    """LLM-powered extractor that summarises user preference facts."""

    def __init__(self, api_key: str, model: str = "Claude-Haiku-4.5") -> None:
        if not api_key:
            raise ValueError("POE_API_KEY is required for FactExtractor")
        self.api_key = api_key
        self.model = model

    def extract(self, items: Iterable[Any], user_profile: Dict[str, Any], max_items: int = 3) -> List[str]:
        candidates = []
        for item in items:
            title = self._get_attr(item, "title")
            summary = self._get_attr(item, "summary") or self._get_attr(item, "ai_summary")
            why = self._get_attr(item, "why_matters_to_you") or self._get_attr(item, "impact_analysis")
            if not title and not summary and not why:
                continue
            candidates.append(
                {
                    "title": title,
                    "summary": summary,
                    "why": why,
                }
            )
            if len(candidates) >= max_items:
                break

        if not candidates:
            return []

        prompt = self._build_prompt(candidates, user_profile)
        response = asyncio.run(self._call_llm(prompt))
        return self._parse_facts(response)

    def _build_prompt(self, candidates: List[Dict[str, str]], user_profile: Dict[str, Any]) -> str:
        user_name = user_profile.get("user_info", {}).get("name", "用户")
        profile_summary = user_profile.get("career_goals", {}).get("primary", "关注AI落地的工程师")

        bullet_lines = []
        for idx, data in enumerate(candidates, start=1):
            bullet_lines.append(
                f"{idx}. 标题：{data['title'] or '（无标题）'}\n"
                f"   摘要：{data['summary'] or '（暂无摘要）'}\n"
                f"   为什么重要：{data['why'] or '（暂无说明）'}"
            )

        return f"""你是个性化偏好分析专家。用户姓名：{user_name}。职业目标：{profile_summary}。

这是他最近标记为“非常重要”的内容：
{chr(10).join(bullet_lines)}

请基于这些内容，提取1-3条**新的**偏好事实，说明用户偏好的主题、风格或需求。结果要求：
- 使用简洁的第一人称描述，例如“我更重视…”，“我希望…”
- 每条事实不超过25个汉字
- 不要重复已有事实
- 输出JSON，格式如下：
{{
  "facts": ["事实1", "事实2"]
}}
只返回JSON，不要额外说明。
"""

    async def _call_llm(self, prompt: str) -> str:
        message = ProtocolMessage(role="user", content=prompt)
        buffer = ""
        async for chunk in get_bot_response(
            messages=[message],
            bot_name=self.model,
            api_key=self.api_key,
        ):
            buffer += chunk.text
        return buffer.strip()

    def _parse_facts(self, response: str) -> List[str]:
        if not response:
            return []
        cleaned = response.replace("```json", "").replace("```", "").strip()
        if not cleaned.startswith("{"):
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1 and end > start:
                cleaned = cleaned[start : end + 1]
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            return []
        facts = data.get("facts", [])
        if not isinstance(facts, list):
            return []
        return [str(fact).strip() for fact in facts if str(fact).strip()]

    def _get_attr(self, item: Any, key: str) -> Optional[str]:
        if isinstance(item, dict):
            return item.get(key)
        return getattr(item, key, None)


__all__ = ["FactExtractor"]
