"""Quick filter agent for pre-screening collected items using a lightweight LLM."""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple

from fastapi_poe import get_bot_response

logger = logging.getLogger(__name__)


@dataclass
class QuickFilterResult:
    """Structured result for a single candidate."""

    index: int
    score: int
    keep: bool
    reason: str


class QuickFilterAgent:
    """LLM-powered triage layer to prune low-value items before heavy processing."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "Claude-Haiku-4.5",
        max_batch_size: int = 12,
        min_score_keep: int = 5,
    ) -> None:
        if not api_key:
            raise ValueError("QuickFilterAgent requires a Poe API key")
        self.api_key = api_key
        self.model_name = model_name
        self.max_batch_size = max_batch_size
        self.min_score_keep = min_score_keep

    def filter_items(
        self,
        raw_items: Sequence[Any],
        top_k: int = 60,
    ) -> Tuple[List[Any], Dict[str, Any]]:
        """
        Use an inexpensive LLM call to quickly classify which raw items are worth
        passing to the expensive batch analysis stage.
        """
        total = len(raw_items)
        if total == 0:
            return [], {"input_total": 0, "kept": 0, "dropped": 0, "avg_score": 0.0}

        if total <= top_k:
            # Nothing to triage when already small enough.
            return list(raw_items), {
                "input_total": total,
                "kept": total,
                "dropped": 0,
                "avg_score": 8.0,
                "strategy": "bypass",
            }

        prepared = self._prepare_payload(raw_items)
        scored: Dict[int, QuickFilterResult] = {}

        for chunk in self._chunk(prepared, self.max_batch_size):
            prompt = self._build_prompt(chunk)
            try:
                response_text = asyncio.run(self._call_poe(prompt))
                records = self._parse_response(response_text)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("Quick filter chunk failed (%s); keeping originals", exc)
                for entry in chunk:
                    idx = entry["index"]
                    if idx not in scored:
                        scored[idx] = QuickFilterResult(index=idx, score=7, keep=True, reason="fallback")
                continue

            for record in records:
                idx = record.index
                if idx not in scored:
                    scored[idx] = record

        if not scored:
            logger.warning("Quick filter produced no scores; returning all items")
            return list(raw_items), {
                "input_total": total,
                "kept": total,
                "dropped": 0,
                "avg_score": 8.0,
                "strategy": "fallback",
            }

        kept_candidates = [res for res in scored.values() if res.keep and res.score >= self.min_score_keep]
        if not kept_candidates:
            # Guarantee we keep something.
            kept_candidates = sorted(scored.values(), key=lambda r: r.score, reverse=True)[:top_k]

        kept_sorted = sorted(kept_candidates, key=lambda r: r.score, reverse=True)
        trimmed = kept_sorted[:top_k]
        kept_indices = {res.index for res in trimmed}

        filtered_items = [raw_items[idx - 1] for idx in sorted(kept_indices) if 0 < idx <= total]
        avg_score = sum(res.score for res in trimmed) / max(len(trimmed), 1)
        dropped = total - len(filtered_items)

        stats = {
            "input_total": total,
            "kept": len(filtered_items),
            "dropped": dropped,
            "avg_score": round(avg_score, 2),
            "strategy": "llm_filter",
        }
        return filtered_items, stats

    def _prepare_payload(self, raw_items: Sequence[Any]) -> List[Dict[str, Any]]:
        prepared = []
        for idx, item in enumerate(raw_items, start=1):
            if isinstance(item, dict):
                getter = item.get
                source = getter("source") or getter("repo_name") or "Unknown"
                title = getter("title") or getter("name") or "(no title)"
                summary = getter("summary") or getter("description") or ""
            else:
                source = getattr(item, "source", getattr(item, "repo_name", "Unknown"))
                title = getattr(item, "title", getattr(item, "name", "(no title)"))
                summary = getattr(item, "summary", getattr(item, "description", ""))

            title = (title or "")[:180]
            summary = (summary or "")[:360]

            prepared.append(
                {
                    "index": idx,
                    "source": source,
                    "title": title,
                    "summary": summary,
                }
            )
        return prepared

    def _build_prompt(self, chunk: List[Dict[str, Any]]) -> str:
        lines = [
            "你是一名AI行业情报助理，目标是在不超过30秒的时间里快速筛选新闻。",
            "请仅输出JSON数组，每个对象包含: index, keep(true/false), score(0-10), reason(<=20字)。",
            f"如果内容和LLM/RAG/Agent/AI工程实践无关，score应低于{self.min_score_keep}并标记keep=false。",
            "优先保留：LLM新技术、RAG实践、Agent架构、评估/监控工具、向量数据库、LangChain/LlamaIndex生态、新模型推理优化。",
            "避免保留：营销软文、纯融资动态、AI政策报道、非技术产品推广。",
            "条目如下：",
        ]
        for entry in chunk:
            lines.append(
                f"{entry['index']}. 来源: {entry['source']}\n标题: {entry['title']}\n摘要: {entry['summary']}"
            )
        lines.append("JSON:")
        return "\n".join(lines)

    async def _call_poe(self, prompt: str) -> str:
        response_text = ""
        async for partial in get_bot_response(
            messages=[{"role": "user", "content": prompt}],
            bot_name=self.model_name,
            api_key=self.api_key,
        ):
            response_text += partial.text
        return response_text

    def _parse_response(self, response_text: str) -> List[QuickFilterResult]:
        cleaned = response_text.strip()
        cleaned = cleaned.replace("```json", "").replace("```", "").strip()
        if not cleaned.startswith("["):
            start = cleaned.find("[")
            end = cleaned.rfind("]")
            if start != -1 and end != -1:
                cleaned = cleaned[start : end + 1]
        data = json.loads(cleaned)
        results: List[QuickFilterResult] = []
        for record in data:
            index = int(record.get("index", 0))
            if index <= 0:
                continue
            score = int(record.get("score", 0))
            keep = bool(record.get("keep", True))
            reason = str(record.get("reason", "")).strip()
            results.append(QuickFilterResult(index=index, score=score, keep=keep, reason=reason))
        return results

    def _chunk(self, data: List[Dict[str, Any]], size: int) -> List[List[Dict[str, Any]]]:
        return [data[i : i + size] for i in range(0, len(data), size)]
