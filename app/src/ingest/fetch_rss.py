"""Generic RSS/Atom fetcher — feed URLs configured via sources.yaml."""

from __future__ import annotations

import asyncio
import html
import re
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

import feedparser
import httpx

from common.logger import get_logger

log = get_logger("auto_matome.ingest.rss")

_TAG_RE = re.compile(r"<[^>]+>")
_SPACE_RE = re.compile(r"\s+")


def _plain_text(value: str) -> str:
    text = html.unescape(_TAG_RE.sub(" ", value))
    return _SPACE_RE.sub(" ", text).strip()


def _iso_date(entry: Any) -> str:
    for key in ("published", "updated", "created"):
        value = entry.get(key)
        if not value:
            continue
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError, IndexError):
            continue
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC).isoformat()
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        value = entry.get(key)
        if not value:
            continue
        return datetime(*value[:6], tzinfo=UTC).isoformat()
    return ""


def _summary(entry: Any) -> str:
    content = entry.get("content") or []
    if content:
        first = content[0]
        if isinstance(first, dict):
            value = first.get("value", "")
            if value:
                return _plain_text(value)[:200]
    return _plain_text(entry.get("summary", "") or entry.get("description", ""))[:200]


async def _fetch_feed(
    client: httpx.AsyncClient, feed_url: str, limit: int
) -> list[dict[str, Any]]:
    try:
        response = await client.get(feed_url)
        response.raise_for_status()
        parsed = feedparser.parse(response.text)
        if getattr(parsed, "bozo", False) and not getattr(parsed, "entries", None):
            raise ValueError(f"unparseable feed: {feed_url}")
    except Exception as exc:
        log.warning("failed to fetch RSS feed", extra={"feed": feed_url, "error": str(exc)})
        return []

    items: list[dict[str, Any]] = []
    for entry in parsed.entries[:limit]:
        url = entry.get("link", "")
        title = str(entry.get("title", "")).strip()
        if not title or not url:
            continue
        items.append(
            {
                "title": title,
                "url": url,
                "published": _iso_date(entry),
                "source_feed": feed_url,
                "summary": _summary(entry),
            }
        )
    log.info("fetched RSS feed", extra={"feed": feed_url, "stories": len(items)})
    return items


async def fetch_rss(
    feeds: list[str],
    limit_per_feed: int = 5,
) -> list[dict[str, Any]]:
    """Fetch recent stories from a list of RSS/Atom feed URLs."""
    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        batches = await asyncio.gather(
            *[_fetch_feed(client, url, limit_per_feed) for url in feeds]
        )

    stories: list[dict[str, Any]] = []
    for batch in batches:
        stories.extend(batch)
    return stories


def fetch(feeds: list[str], limit_per_feed: int = 5) -> list[dict[str, Any]]:
    """Synchronous wrapper."""
    return asyncio.run(fetch_rss(feeds=feeds, limit_per_feed=limit_per_feed))
