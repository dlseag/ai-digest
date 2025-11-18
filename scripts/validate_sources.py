#!/usr/bin/env python
"""
Validate configured information sources for ai-digest.

Example:
    python scripts/validate_sources.py --categories rss_feeds,news_feeds --show-errors-only
"""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import logging
import re
import sys
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Iterable

import requests
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "sources.yaml"
REPORT_PATH = PROJECT_ROOT / "tmp" / "source_validation_report.json"

USER_AGENT = "ai-digest-validator/1.0 (+https://github.com/dlseag/ai-digest)"

RSS_MARKERS = ("<rss", "<feed", "<rdf", "<item", "<entry")
DATE_PATTERNS = (
    re.compile(r"<pubDate>(?P<value>[^<]+)</pubDate>", re.IGNORECASE),
    re.compile(r"<updated>(?P<value>[^<]+)</updated>", re.IGNORECASE),
    re.compile(r"<lastBuildDate>(?P<value>[^<]+)</lastBuildDate>", re.IGNORECASE),
    re.compile(r"<dc:date>(?P<value>[^<]+)</dc:date>", re.IGNORECASE),
)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate ai-digest sources.yaml feeds.")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to sources.yaml (default: %(default)s)",
    )
    parser.add_argument(
        "--categories",
        type=str,
        default="rss_feeds,news_feeds,leaderboards,hacker_news,producthunt,twitter",
        help="Comma separated list of top-level categories to validate.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=12.0,
        help="HTTP timeout per request in seconds.",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=8,
        help="Concurrent workers for HTTP requests.",
    )
    parser.add_argument(
        "--include-disabled",
        action="store_true",
        help="Include entries where enabled=false.",
    )
    parser.add_argument(
        "--head",
        action="store_true",
        help="Attempt HEAD before GET requests.",
    )
    parser.add_argument(
        "--show-errors-only",
        action="store_true",
        help="Only print feeds with warnings or errors.",
    )
    return parser.parse_args(argv)


def load_sources(config_path: Path, categories: list[str], include_disabled: bool) -> list[dict[str, Any]]:
    with config_path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}

    sources: list[dict[str, Any]] = []
    for category in categories:
        entries = data.get(category, [])
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue

            enabled = entry.get("enabled", True)
            if not include_disabled and enabled is False:
                continue

            url = entry.get("url")
            if not url:
                continue

            sources.append(
                {
                    "category": category,
                    "name": entry.get("name") or entry.get("repo") or "unknown",
                    "url": url,
                }
            )
    return sources


def try_parse_date(raw: str) -> datetime | None:
    raw = raw.strip()
    try:
        dt = parsedate_to_datetime(raw)
    except (TypeError, ValueError):
        return None
    if dt and dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def sniff_latest_date(xml_text: str) -> datetime | None:
    for pattern in DATE_PATTERNS:
        match = pattern.search(xml_text)
        if match:
            dt = try_parse_date(match.group("value"))
            if dt:
                return dt
    return None


def fetch_feed(url: str, timeout: float, head_first: bool) -> tuple[int, str, str]:
    session = requests.Session()
    headers = {"User-Agent": USER_AGENT, "Accept": "*/*"}

    if head_first:
        try:
            head_resp = session.head(url, timeout=timeout, allow_redirects=True, headers=headers)
            if head_resp.status_code < 400:
                content_type = head_resp.headers.get("Content-Type", "")
                if "xml" in content_type or "text" in content_type:
                    content_length = int(head_resp.headers.get("Content-Length", "0") or 0)
                    if content_length > 0:
                        return head_resp.status_code, content_type, ""
        except requests.RequestException:
            pass

    resp = session.get(url, timeout=timeout, allow_redirects=True, headers=headers)
    resp.raise_for_status()
    content_type = resp.headers.get("Content-Type", "")
    text = resp.text if ("xml" in content_type or "text" in content_type) else ""
    return resp.status_code, content_type, text


def evaluate_source(source: dict[str, Any], timeout: float, head_first: bool) -> dict[str, Any]:
    url = source["url"]
    result: dict[str, Any] = {
        "category": source["category"],
        "name": source["name"],
        "url": url,
        "status": None,
        "content_type": None,
        "size_bytes": None,
        "latest_date": None,
        "contains_rss": False,
        "warning": None,
    }

    try:
        status, content_type, text = fetch_feed(url, timeout=timeout, head_first=head_first)
        result["status"] = status
        result["content_type"] = content_type
        if text:
            result["size_bytes"] = len(text.encode("utf-8", errors="ignore"))
            lowered = text.lower()
            result["contains_rss"] = any(marker in lowered for marker in RSS_MARKERS)
            latest = sniff_latest_date(text)
            if latest:
                result["latest_date"] = latest.isoformat()
            if not result["contains_rss"]:
                result["warning"] = "Payload missing RSS/Atom markers (likely HTML)."
        else:
            result["warning"] = "No textual body detected (HEAD success or binary response)."
    except requests.RequestException as exc:
        result["warning"] = f"Request failed: {exc}"

    return result


def ensure_tmp() -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    categories = [part.strip() for part in args.categories.split(",") if part.strip()]
    sources = load_sources(args.config, categories, args.include_disabled)
    if not sources:
        logging.error("No sources found for categories %s", categories)
        return 1

    logging.info("Validating %d sources from %s", len(sources), args.config)

    results: list[dict[str, Any]] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.max_workers) as pool:
        futures = [
            pool.submit(evaluate_source, source, args.timeout, args.head)
            for source in sources
        ]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    ensure_tmp()
    REPORT_PATH.write_text(json.dumps(results, indent=2), encoding="utf-8")
    logging.info("Report written to %s", REPORT_PATH)

    header = f"{'Category':20} {'Name':35} {'Status':>6} {'Type':18} {'Latest':24} Warning"
    print(header)
    print("-" * len(header))

    printed = 0
    for item in sorted(results, key=lambda x: (x['category'], x['name'].lower())):
        warning = item.get("warning")
        if args.show_errors_only and not warning:
            continue
        status = item.get("status")
        status_str = str(status) if status is not None else "---"
        latest = item.get("latest_date") or "-"
        row = f"{item['category'][:20]:20} {item['name'][:35]:35} {status_str:>6} {str(item.get('content_type') or '-')[:18]:18} {latest[:24]:24} {warning or ''}"
        print(row)
        printed += 1

    if args.show_errors_only and printed == 0:
        print("All feeds look healthy.")

    alive = sum(1 for item in results if item.get("status") and item["status"] < 400)
    warnings = sum(1 for item in results if item.get("warning"))
    logging.info("Alive feeds: %d/%d (warnings: %d)", alive, len(results), warnings)

    return 0


if __name__ == "__main__":
    sys.exit(main())
