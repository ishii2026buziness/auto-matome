"""Fetch top posts + comments from Reddit using the public .json API.

No API credentials required. Uses the unofficial JSON endpoint:
  https://www.reddit.com/r/<subreddit>/top.json  → post listing
  https://www.reddit.com/r/<subreddit>/comments/<id>/.json → post + comments
"""

from __future__ import annotations

import asyncio
import html
import re
from typing import Any

import httpx

from common.logger import get_logger

log = get_logger("auto_matome.ingest.reddit")

# Subreddits to monitor — tech/AI/dev focused, good for 2ch-style matome
DEFAULT_SUBREDDITS = [
    "programming",
    "technology",
    "artificial",
    "MachineLearning",
    "webdev",
    "LocalLLaMA",
]

# Reddit blocks default User-Agent; use a descriptive custom one
_HEADERS = {"User-Agent": "auto-matome-bot/1.0 (aggregator; read-only)"}
_BASE = "https://www.reddit.com"


_YOUTUBE_RE = re.compile(
    r"(?:youtube\.com/watch\?(?:.*&)?v=|youtu\.be/)([A-Za-z0-9_-]{11})"
)


def _extract_media(d: dict) -> dict:
    """Extract media metadata from a Reddit post data dict.

    Returns a dict with:
      - image_url: best available image URL (preview > thumbnail), or None
      - youtube_id: YouTube video ID if post links to YouTube, or None
    """
    # Best preview image (HTML entities decoded)
    image_url: str | None = None
    preview = d.get("preview", {})
    images = preview.get("images", [])
    if images:
        raw = images[0].get("source", {}).get("url", "")
        if raw:
            image_url = html.unescape(raw)
    # Fall back to thumbnail if it looks like a real URL
    if not image_url:
        thumb = d.get("thumbnail", "")
        if thumb and thumb.startswith("http"):
            image_url = thumb

    # YouTube video ID
    youtube_id: str | None = None
    url = d.get("url", "")
    m = _YOUTUBE_RE.search(url)
    if m:
        youtube_id = m.group(1)

    return {"image_url": image_url, "youtube_id": youtube_id}


def _extract_top_comments(comment_listing: list[dict], max_comments: int = 5) -> list[str]:
    """Extract top-level comment bodies from a Reddit comment listing."""
    comments: list[str] = []
    if not comment_listing or len(comment_listing) < 2:
        return comments
    children = comment_listing[1].get("data", {}).get("children", [])
    for child in children:
        if len(comments) >= max_comments:
            break
        data = child.get("data", {})
        if child.get("kind") != "t1":
            continue
        body = data.get("body", "").strip()
        # Skip deleted/removed/very short
        if body in ("", "[deleted]", "[removed]") or len(body) < 10:
            continue
        comments.append(body)
    return comments


async def _fetch_post_with_comments(
    client: httpx.AsyncClient,
    permalink: str,
    max_comments: int = 5,
) -> list[str]:
    """Fetch comments for a single post via permalink.json."""
    url = f"{_BASE}{permalink}.json?limit={max_comments}&sort=top"
    try:
        resp = await client.get(url)
        resp.raise_for_status()
        data = resp.json()
        return _extract_top_comments(data)
    except Exception as exc:
        log.warning("failed to fetch comments", extra={"permalink": permalink, "error": str(exc)})
        return []


async def fetch_reddit(
    subreddits: list[str] | None = None,
    limit_per_sub: int = 10,
    max_comments: int = 5,
    timeframe: str = "day",
) -> list[dict[str, Any]]:
    """Fetch top posts + comments from configured subreddits.

    Returns:
        List of dicts with: title, url, score, subreddit, comments (list[str]).
    """
    subs = subreddits or DEFAULT_SUBREDDITS
    timeout = httpx.Timeout(15.0, connect=5.0)

    async with httpx.AsyncClient(headers=_HEADERS, timeout=timeout) as client:
        # Step 1: fetch post listings for all subreddits in parallel
        listing_tasks = [
            client.get(f"{_BASE}/r/{sub}/top.json?t={timeframe}&limit={limit_per_sub}")
            for sub in subs
        ]
        listing_responses = await asyncio.gather(*listing_tasks, return_exceptions=True)

        # Parse listings into post stubs
        posts: list[dict[str, Any]] = []
        for sub, resp in zip(subs, listing_responses):
            if isinstance(resp, Exception):
                log.warning("failed to fetch subreddit", extra={"sub": sub, "error": str(resp)})
                continue
            try:
                resp.raise_for_status()
                children = resp.json()["data"]["children"]
            except Exception as exc:
                log.warning("bad listing response", extra={"sub": sub, "error": str(exc)})
                continue
            for child in children:
                d = child.get("data", {})
                url = d.get("url", "")
                permalink = d.get("permalink", "")
                if not url or not permalink:
                    continue
                posts.append({
                    "title": d.get("title", ""),
                    "url": url,
                    "score": d.get("score", 0),
                    "subreddit": sub,
                    "permalink": permalink,
                    "num_comments": d.get("num_comments", 0),
                    **_extract_media(d),
                })
            log.info("fetched subreddit listing", extra={"sub": sub, "posts": len(children)})

        # Step 2: fetch comments for each post in parallel
        comment_tasks = [
            _fetch_post_with_comments(client, p["permalink"], max_comments)
            for p in posts
        ]
        all_comments = await asyncio.gather(*comment_tasks)

    # Merge comments into post dicts, drop permalink (internal)
    results: list[dict[str, Any]] = []
    for post, comments in zip(posts, all_comments):
        results.append({
            "title": post["title"],
            "url": post["url"],
            "score": post["score"],
            "subreddit": post["subreddit"],
            "num_comments": post["num_comments"],
            "comments": comments,
            "image_url": post.get("image_url"),
            "youtube_id": post.get("youtube_id"),
        })

    log.info("reddit fetch complete", extra={"posts": len(results)})
    return results


def fetch(subreddits: list[str] | None = None, limit_per_sub: int = 10) -> list[dict[str, Any]]:
    """Synchronous wrapper."""
    return asyncio.run(fetch_reddit(subreddits=subreddits, limit_per_sub=limit_per_sub))
