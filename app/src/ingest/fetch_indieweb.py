"""Fetch posts from IndieWeb / Auto Matome RSS and Atom feeds."""

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

log = get_logger("auto_matome.ingest.indieweb")

FEEDS: tuple[str, ...] = (
    "https://aaronparecki.com/feed.xml",
    "https://adactio.com/journal/rss",
    "https://benhoyt.com/writings/rss.xml",
    "https://daverupert.com/atom.xml",
    "https://tantek.com/updates.atom",
    "https://jamesg.blog/feed.xml",
    "https://minutestomidnight.co.uk/feed.xml",
    "https://bacardi55.io/index.xml",
    "https://blog.jim-nielsen.com/feed.xml",
)

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


def _author(entry: Any) -> str:
    for key in ("author", "dc_creator"):
        value = entry.get(key)
        if value:
            return str(value)
    authors = entry.get("authors") or []
    if authors:
        first = authors[0]
        if isinstance(first, dict) and first.get("name"):
            return str(first["name"])
    return ""


async def _fetch_feed(client: httpx.AsyncClient, feed_url: str) -> list[dict[str, Any]]:
    try:
        response = await client.get(feed_url)
        response.raise_for_status()
        parsed = feedparser.parse(response.text)
        if getattr(parsed, "bozo", False) and not getattr(parsed, "entries", None):
            raise ValueError(f"unparseable feed: {feed_url}")
    except Exception as exc:
        log.warning("failed to fetch IndieWeb feed", extra={"feed": feed_url, "error": str(exc)})
        return []

    items: list[dict[str, Any]] = []
    for entry in parsed.entries:
        url = entry.get("link", "")
        title = str(entry.get("title", "")).strip()
        if not title or not url:
            continue
        items.append(
            {
                "title": title,
                "url": url,
                "published": _iso_date(entry),
                "author": _author(entry),
                "source_feed": feed_url,
                "summary": _summary(entry),
            }
        )
    log.info("fetched IndieWeb feed", extra={"feed": feed_url, "stories": len(items)})
    return items


async def fetch_indieweb(limit_per_feed: int = 10) -> list[dict[str, Any]]:
    """Fetch recent stories from hardcoded IndieWeb feeds."""
    timeout = httpx.Timeout(20.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        batches = await asyncio.gather(*[_fetch_feed(client, feed) for feed in FEEDS])

    stories: list[dict[str, Any]] = []
    for batch in batches:
        stories.extend(batch[:limit_per_feed])
    return stories


def fetch(limit_per_feed: int = 10) -> list[dict[str, Any]]:
    """Synchronous wrapper for simple scripts."""
    return asyncio.run(fetch_indieweb(limit_per_feed=limit_per_feed))
