"""Fetch top Hacker News stories via the Firebase API."""

from __future__ import annotations

import asyncio
import os
from typing import Any

import httpx


async def fetch_hn(limit: int = 30) -> list[dict[str, Any]]:
    """Fetch top Hacker News stories.

    Returns:
        List of dicts with title, url, score, descendants, by.
    """
    base_url = os.getenv("AM_HN_API_BASE", "https://hacker-news.firebaseio.com/v0")
    timeout = httpx.Timeout(10.0, connect=5.0)

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout) as client:
        response = await client.get("/topstories.json")
        response.raise_for_status()
        story_ids = response.json()[:limit]

        tasks = [client.get(f"/item/{story_id}.json") for story_id in story_ids]
        responses = await asyncio.gather(*tasks)

    stories: list[dict[str, Any]] = []
    for response in responses:
        response.raise_for_status()
        item = response.json()
        if not isinstance(item, dict) or item.get("type") != "story":
            continue
        stories.append(
            {
                "title": item.get("title", ""),
                "url": item.get("url") or f"https://news.ycombinator.com/item?id={item.get('id')}",
                "score": item.get("score", 0),
                "descendants": item.get("descendants", 0),
                "by": item.get("by", ""),
            }
        )

    return stories


def fetch(limit: int = 30) -> list[dict[str, Any]]:
    """Synchronous wrapper for simple scripts."""
    return asyncio.run(fetch_hn(limit=limit))
