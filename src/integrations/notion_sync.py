"""
Utility to publish reports to Notion databases.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime
from typing import Dict, List, Optional

try:
    from notion_client import Client
except ImportError:  # pragma: no cover - handled gracefully at runtime
    Client = None  # type: ignore


class NotionSyncService:
    """Minimal wrapper around the Notion API for storing briefing reports."""

    MAX_BLOCKS = 80  # keep pages lightweight to avoid API limits
    MAX_TEXT_CHARS = 1800  # Notion rich text limit per block is 2000

    def __init__(
        self,
        api_token: Optional[str] = None,
        database_id: Optional[str] = None,
    ) -> None:
        self.logger = logging.getLogger(self.__class__.__name__)
        self.api_token = api_token or os.getenv("NOTION_API_TOKEN")
        self.database_id = database_id or os.getenv("NOTION_DATABASE_ID")
        self.client: Optional[Client] = None

        if not Client:
            self.logger.debug("notion-client 未安装，跳过 Notion 同步。")
            return

        if not self.api_token or not self.database_id:
            self.logger.debug("未配置 NOTION_API_TOKEN 或 NOTION_DATABASE_ID，跳过 Notion 同步。")
            return

        try:
            # log_level to WARNING to reduce noise
            self.client = Client(auth=self.api_token, log_level=logging.WARNING)
        except Exception as exc:  # pragma: no cover - network/init issues
            self.logger.warning("初始化 Notion Client 失败: %s", exc)
            self.client = None

    @property
    def is_enabled(self) -> bool:
        return self.client is not None and bool(self.database_id)

    def sync_report(
        self,
        title: str,
        markdown_content: str,
        metadata: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Send the rendered markdown to Notion."""
        if not self.is_enabled:
            self.logger.debug("Notion 同步未启用，跳过。")
            return False

        properties = {
            "Name": {
                "title": [
                    {
                        "type": "text",
                        "text": {"content": title[:200]},
                    }
                ]
            }
        }

        children: List[Dict] = []
        metadata_block = self._build_metadata_block(metadata)
        if metadata_block:
            children.append(metadata_block)

        children.extend(self._markdown_to_blocks(markdown_content))

        try:
            self.client.pages.create(  # type: ignore[union-attr]
                parent={"database_id": self.database_id},
                properties=properties,
                children=children[: self.MAX_BLOCKS],
            )
            self.logger.info("✓ 已同步到 Notion：%s", title)
            return True
        except Exception as exc:  # pragma: no cover - API failure
            self.logger.warning("⚠️ Notion 同步失败：%s", exc)
            return False

    def _build_metadata_block(self, metadata: Optional[Dict[str, str]]) -> Optional[Dict]:
        if not metadata:
            return None

        pieces: List[str] = []
        report_date = metadata.get("report_date")
        if report_date:
            pieces.append(f"🗓️ Report Date: {report_date}")
        markdown_path = metadata.get("markdown_path")
        if markdown_path:
            pieces.append(f"📝 Markdown: {markdown_path}")
        html_path = metadata.get("html_path")
        if html_path:
            pieces.append(f"🌐 HTML: {html_path}")
        total_chars = metadata.get("total_chars")
        if total_chars:
            pieces.append(f"🔢 Characters: {total_chars}")

        if not pieces:
            return None

        content = " | ".join(pieces)
        return self._paragraph_block(content)

    def _markdown_to_blocks(self, markdown_content: str) -> List[Dict]:
        """Convert markdown text into simple paragraph blocks."""
        paragraphs: List[str] = []
        for chunk in markdown_content.split("\n\n"):
            text = chunk.strip()
            if not text:
                continue
            # Collapse excessive whitespace
            paragraphs.append(" ".join(text.split()))

        blocks: List[Dict] = []
        for paragraph in paragraphs:
            for piece in self._chunk_text(paragraph, self.MAX_TEXT_CHARS):
                blocks.append(self._paragraph_block(piece))
                if len(blocks) >= self.MAX_BLOCKS:
                    return blocks
        return blocks

    def _chunk_text(self, text: str, max_chars: int) -> List[str]:
        return [text[i : i + max_chars] for i in range(0, len(text), max_chars)] or [text]

    def _paragraph_block(self, content: str) -> Dict:
        return {
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {
                        "type": "text",
                        "text": {"content": content},
                    }
                ]
            },
        }


def build_notion_title(date_str: str) -> str:
    """Helper to keep Notion page titles consistent."""
    return f"AI 情报简报 - {date_str}"

