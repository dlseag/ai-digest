"""
Utilities for deduplicating content items across the AI Digest pipeline.
"""

from __future__ import annotations

from typing import Any, Callable, Iterable, List, Optional, Set


def normalize_url(url: Optional[str]) -> str:
    """
    Normalize URL strings for deduplication purposes.

    - Trim whitespace
    - Remove trailing slashes
    - Convert None to empty string
    """
    if not url:
        return ""
    normalized = url.strip()
    while normalized.endswith("/"):
        normalized = normalized[:-1]
    return normalized


def make_dedupe_key(
    item: Any,
    *,
    url_attr: str = "url",
    link_attr: str = "link",
    title_attr: str = "title",
) -> str:
    """
    Generate a stable deduplication key for arbitrary content objects.
    """
    url = getattr(item, url_attr, None) or getattr(item, link_attr, None)
    normalized_url = normalize_url(url)
    title = getattr(item, title_attr, "") or ""
    if isinstance(title, str):
        title = title.strip()
    return f"{normalized_url}:{title}"


def mark_unique(
    item: Any,
    used_keys: Set[str],
    key_fn: Optional[Callable[[Any], str]] = None,
) -> bool:
    """
    Add the item's dedupe key into ``used_keys`` if it is new.

    Returns True if the item was not seen before, otherwise False.
    """
    key_builder = key_fn or make_dedupe_key
    dedupe_key = key_builder(item)
    if dedupe_key in used_keys:
        return False
    used_keys.add(dedupe_key)
    return True


def unique_items(
    items: Iterable[Any],
    key_fn: Callable[[Any], str],
) -> List[Any]:
    """
    Return a list of items with duplicates removed using the provided key function.
    """
    seen: Set[str] = set()
    unique: List[Any] = []
    for item in items:
        key = key_fn(item)
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique

