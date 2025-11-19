from types import SimpleNamespace

from src.utils.dedupe import make_dedupe_key, mark_unique, normalize_url, unique_items


def test_normalize_url_strips_trailing_slash():
    assert normalize_url("https://example.com/") == "https://example.com"
    assert normalize_url("   https://example.com/path  ") == "https://example.com/path"
    assert normalize_url(None) == ""


def test_make_dedupe_key_uses_url_or_link():
    item_with_url = SimpleNamespace(url="https://ai.com", title="Hello")
    assert make_dedupe_key(item_with_url) == "https://ai.com:Hello"

    item_with_link = SimpleNamespace(link="https://ai.com/news", title="World")
    assert make_dedupe_key(item_with_link) == "https://ai.com/news:World"


def test_mark_unique_marks_and_detects_duplicates():
    used = set()
    item = SimpleNamespace(url="https://dup.com", title="Duplicate")

    assert mark_unique(item, used) is True
    assert mark_unique(item, used) is False
    assert len(used) == 1


def test_unique_items_returns_only_one_entry_per_key():
    items = [
        SimpleNamespace(url="https://dup.com/", title="A"),
        SimpleNamespace(url="https://dup.com", title="B"),
        SimpleNamespace(url="https://unique.com", title="C"),
    ]
    unique = unique_items(items, lambda x: normalize_url(x.url))
    assert len(unique) == 2
    assert unique[0].title == "A"

