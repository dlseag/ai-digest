"""
Voice Script Generator
将Markdown周报转换为适合口播的中文文字稿。
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class HeadlineItem:
    index: int
    title: str
    source: str
    published: str
    summary: str


@dataclass
class SimpleItem:
    title: str
    source: str
    summary: str


class VoiceScriptGenerator:
    """根据Markdown周报生成中文口播稿"""

    def __init__(
        self,
        intro_template: Optional[str] = None,
        outro_template: Optional[str] = None,
    ) -> None:
        self.intro_template = (
            intro_template
            or "大家好，这里是{date}的AI工程师周报口播稿。我们先从本周的重点新闻开始。"
        )
        self.outro_template = (
            outro_template
            or "以上就是本期AI工程师周报口播稿。感谢收听，我们下次再见。"
        )

        self.heading_pattern = re.compile(r"^(#{2,})\s+(.*)")
        self.headline_pattern = re.compile(r"^####\s+(\d+)\.\s+(.*)")
        self.bold_field_pattern = re.compile(r"^\*\*(.+?)\*\*:\s*(.*)")

    # ------------------------------------------------------------------ #
    def generate(self, markdown_text: str, output_path: str) -> None:
        """根据Markdown内容生成口播稿"""
        try:
            context = self._parse_markdown(markdown_text)
            script = self._build_script(context)
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(script)
            logger.info("✓ 口播稿已生成: %s", output_path)
        except Exception as exc:  # pragma: no cover - 日志记录
            logger.warning("生成口播稿失败: %s", exc, exc_info=True)

    # ------------------------------------------------------------------ #
    def _build_script(self, context: Dict[str, List]) -> str:
        date_str = datetime.now().strftime("%Y年%m月%d日")
        parts: List[str] = [self.intro_template.format(date=date_str), ""]

        # Top headlines
        headlines: List[HeadlineItem] = context.get("headlines", [])
        if headlines:
            parts.append("本周十条重点头条分别是：")
            for item in headlines:
                sentence = (
                    f"第{item.index}条头条，来自{item.source}，发布时间 {item.published}。"
                    f"标题：{item.title}。"
                    f"核心内容：{item.summary}"
                )
                parts.append(self._normalize_sentence(sentence))
            parts.append("")

        # 深度洞察
        insights: List[SimpleItem] = context.get("insights", [])
        if insights:
            parts.append("接下来是深度洞察与战术精选：")
            for idx, item in enumerate(insights, 1):
                sentence = (
                    f"第{idx}篇精选文章，来自{item.source}，标题《{item.title}》。"
                    f"主要观点：{item.summary}"
                )
                parts.append(self._normalize_sentence(sentence))
            parts.append("")

        # 精选项目
        projects: List[SimpleItem] = context.get("projects", [])
        if projects:
            parts.append("本周值得关注的开源或社区项目包括：")
            for idx, item in enumerate(projects, 1):
                sentence = (
                    f"项目{idx}：{item.source}发布的《{item.title}》。"
                    f"项目亮点：{item.summary}"
                )
                parts.append(self._normalize_sentence(sentence))
            parts.append("")

        # 框架更新
        frameworks: List[SimpleItem] = context.get("frameworks", [])
        if frameworks:
            parts.append("框架与工具方面的关键更新：")
            for idx, item in enumerate(frameworks, 1):
                sentence = (
                    f"更新{idx}：{item.source}发布《{item.title}》。"
                    f"更新内容：{item.summary}"
                )
                parts.append(self._normalize_sentence(sentence))
            parts.append("")

        # 新模型
        models: List[SimpleItem] = context.get("models", [])
        if models:
            parts.append("新模型与平台的动态：")
            for idx, item in enumerate(models, 1):
                sentence = (
                    f"模型{idx}：{item.source}推出《{item.title}》。"
                    f"核心信息：{item.summary}"
                )
                parts.append(self._normalize_sentence(sentence))
            parts.append("")

        # 市场洞察
        market: List[SimpleItem] = context.get("market", [])
        if market:
            parts.append("最后补充几条市场洞察：")
            for idx, item in enumerate(market, 1):
                sentence = (
                    f"洞察{idx}：{item.source}发布《{item.title}》。"
                    f"要点：{item.summary}"
                )
                parts.append(self._normalize_sentence(sentence))
            parts.append("")

        parts.append(self.outro_template)
        script = "\n".join(parts).strip() + "\n"
        return script

    # ------------------------------------------------------------------ #
    def _parse_markdown(self, markdown_text: str) -> Dict[str, List]:
        """将Markdown内容解析为结构化数据"""
        lines = markdown_text.splitlines()
        idx = 0
        total = len(lines)

        context: Dict[str, List] = {
            "headlines": [],
            "insights": [],
            "projects": [],
            "frameworks": [],
            "models": [],
            "market": [],
        }

        current_section = None
        while idx < total:
            line = lines[idx].strip()

            # 识别 section
            heading_match = self.heading_pattern.match(line)
            if heading_match:
                hashes, title = heading_match.groups()
                level = len(hashes)
                if level == 2:
                    current_section = self._normalize_title(title)
                    idx += 1
                    continue

            # 解析头条
            if current_section == "本周头条":
                headline_match = self.headline_pattern.match(line)
                if headline_match:
                    index = int(headline_match.group(1))
                    title = headline_match.group(2).strip()
                    idx += 1
                    meta = self._collect_metadata(lines, idx)
                    idx = meta["next_index"]
                    summary = meta.get("summary", "")
                    context["headlines"].append(
                        HeadlineItem(
                            index=index,
                            title=title,
                            source=meta.get("source", ""),
                            published=meta.get("published", ""),
                            summary=summary,
                        )
                    )
                    continue

            # 解析其他 section 中的条目
            if current_section in (
                "深度洞察与战术 (精选技术文章)",
                "本周精选项目 (OSS Spotlight)",
                "框架与工具更新 (Framework & Tooling Corner)",
                "新模型与平台 (New Models & Platforms)",
                "市场动态与趋势",
            ):
                if line.startswith("#### "):
                    title = line.lstrip("#").strip()
                    idx += 1
                    meta = self._collect_metadata(lines, idx)
                    idx = meta["next_index"]
                    item = SimpleItem(
                        title=title,
                        source=meta.get("source", ""),
                        summary=meta.get("summary", ""),
                    )
                    key = self._section_key(current_section)
                    context[key].append(item)
                    continue

            idx += 1

        return context

    def _collect_metadata(self, lines: List[str], start_index: int) -> Dict[str, str]:
        """收集来源/发布时间/摘要等字段"""
        meta: Dict[str, str] = {}
        idx = start_index
        total = len(lines)
        summary_lines: List[str] = []
        capturing_summary = False

        while idx < total:
            text = lines[idx].strip()

            if text.startswith("---"):
                idx += 1
                break

            if text.startswith("**"):
                match = self.bold_field_pattern.match(text)
                if match:
                    field, value = match.groups()
                    field = field.strip()
                    value = value.strip()

                    # 支持单行多个字段（通过 | 分隔）
                    segments = [seg.strip() for seg in re.split(r"\|\s*", value) if seg.strip()]
                    if not segments:
                        segments = [value]

                    capturing_summary = False
                    for seg in segments:
                        sub_match = self.bold_field_pattern.match(seg)
                        if sub_match:
                            sub_field, sub_value = sub_match.groups()
                            capturing_summary = self._process_field(
                                meta, sub_field.strip(), sub_value.strip(), summary_lines
                            )
                        else:
                            capturing_summary = self._process_field(
                                meta, field, seg, summary_lines
                            )

                    idx += 1
                    continue

            if capturing_summary:
                if text:
                    summary_lines.append(text)
                idx += 1
                continue

            if not text:
                idx += 1
                continue

            idx += 1

        meta["summary"] = self._normalize_sentence(" ".join(summary_lines))
        meta["next_index"] = idx
        return meta

    def _process_field(self, meta: Dict[str, str], field: str, value: str, summary_lines: List[str]) -> bool:
        """处理单个字段，返回是否进入摘要采集模式"""
        normalized_value = self._strip_markdown_links(value)
        field_key = self._normalize_field(field)

        if field in ("📝 摘要", "核心观点"):
            if normalized_value:
                summary_lines.append(normalized_value)
            return True

        if field_key:
            meta[field_key] = normalized_value
        return False

    def _strip_markdown_links(self, text: str) -> str:
        def replace_link(match: re.Match[str]) -> str:
            label, url = match.groups()
            label = label.strip()
            url = url.strip()
            if not label:
                return url
            return f"{label}（链接：{url}）"

        text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", replace_link, text)
        text = text.replace("**", "").replace("__", "")
        text = text.strip()

        # 移除多余的分隔符
        text = re.sub(r"\s*\|\s*", "，", text)
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    # ------------------------------------------------------------------ #
    def _normalize_field(self, field: str) -> str:
        mapping = {
            "来源": "source",
            "发布": "published",
            "链接": "link",
        }
        return mapping.get(field, field)

    def _section_key(self, section_name: str) -> str:
        if section_name.startswith("深度洞察"):
            return "insights"
        if section_name.startswith("本周精选项目"):
            return "projects"
        if section_name.startswith("框架与工具更新"):
            return "frameworks"
        if section_name.startswith("新模型与平台"):
            return "models"
        if section_name.startswith("市场动态"):
            return "market"
        return "other"

    def _normalize_title(self, title: str) -> str:
        return title.replace("🔥", "").replace("📊", "").replace("📈", "").replace("🔬", "").replace("📚", "").replace("🛠️", "").strip()

    def _normalize_sentence(self, text: str) -> str:
        text = text.replace("**", "").replace("__", "")
        text = re.sub(r"\s+", " ", text)
        return text.strip()



