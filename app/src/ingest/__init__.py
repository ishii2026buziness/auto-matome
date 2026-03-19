"""Ingest layer — fetch content from overseas sources (IndieWeb, Reddit, HN, X)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, Callable, Coroutine

import yaml

from common.logger import get_logger

log = get_logger("auto_matome.ingest")

_CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "sources.yaml"

# Registry: source name → async fetch function
# Each function must accept **params and return list[dict]
def _registry() -> dict[str, Callable[..., Coroutine[Any, Any, list[dict]]]]:
    from ingest.fetch_hn import fetch_hn
    from ingest.fetch_indieweb import fetch_indieweb
    from ingest.fetch_reddit import fetch_reddit
    from ingest.fetch_rss import fetch_rss

    return {
        "hn": fetch_hn,
        "indieweb": fetch_indieweb,
        "reddit": fetch_reddit,
        "rss": fetch_rss,
    }


async def fetch_all(config_path: Path | None = None) -> list[dict]:
    """Fetch all enabled sources from config/sources.yaml in parallel.

    Returns a flat list of story dicts, each with a '_source' key added.
    """
    path = config_path or _CONFIG_PATH
    with open(path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    registry = _registry()
    tasks: list[Coroutine[Any, Any, list[dict]]] = []
    source_names: list[str] = []

    for entry in config.get("sources", []):
        if not entry.get("enabled", True):
            continue
        name = entry["name"]
        params = entry.get("params") or {}
        fetcher = registry.get(name)
        if fetcher is None:
            log.warning("unknown source in config, skipping", extra={"name": name})
            continue
        tasks.append(fetcher(**params))
        source_names.append(name)

    results = await asyncio.gather(*tasks, return_exceptions=True)

    stories: list[dict] = []
    for name, result in zip(source_names, results):
        if isinstance(result, Exception):
            log.error("source fetch failed", extra={"source": name, "error": str(result)})
            continue
        log.info("source fetched", extra={"source": name, "count": len(result)})
        for story in result:
            stories.append({**story, "_source": name})

    return stories
