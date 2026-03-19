"""Deduplicate articles by normalized URL across sources and across runs."""

from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from common.logger import get_logger

log = get_logger("auto_matome.curate.dedup")

# Persistent store of seen URLs (one JSON file per pipeline root)
_DEFAULT_SEEN_PATH = Path(__file__).resolve().parents[2] / "output" / ".seen_urls.json"


def normalize_url(url: str) -> str:
    """Normalize URL for dedup comparison.

    Strips trailing slashes, fragments, query params (utm_*), and lowercases host.
    """
    parsed = urlparse(url.strip())
    # Lowercase scheme + host
    scheme = parsed.scheme.lower() or "https"
    netloc = parsed.netloc.lower()
    # Remove www. prefix
    netloc = re.sub(r"^www\.", "", netloc)
    # Strip fragment
    # Filter out tracking query params
    path = parsed.path.rstrip("/") or "/"
    return urlunparse((scheme, netloc, path, "", "", ""))


def _load_seen(path: Path, *, current_date: date) -> set[str]:
    today = current_date.isoformat()
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            # New format: {"date": "...", "urls": [...]}
            if isinstance(data, dict):
                if data.get("date") == today:
                    return set(data.get("urls", []))
                log.info("seen_urls date changed, resetting", extra={"old": data.get("date"), "new": today})
                return set()
            # Legacy format: plain list
            return set(data)
        except (json.JSONDecodeError, TypeError):
            log.warning("corrupt seen_urls file, starting fresh")
    return set()


def _save_seen(seen: set[str], path: Path, *, current_date: date) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    data = {"date": current_date.isoformat(), "urls": sorted(seen)}
    path.write_text(json.dumps(data), encoding="utf-8")


def dedup_stories(
    stories: list[dict],
    *,
    seen_path: Path | None = None,
    persist: bool = True,
    current_date: date | None = None,
) -> list[dict]:
    """Remove duplicate stories by normalized URL.

    Deduplicates within the batch and against previously seen URLs.
    Returns only new, unique stories. Persists the updated seen set.
    """
    path = seen_path or _DEFAULT_SEEN_PATH
    active_date = current_date or date.today()
    seen = _load_seen(path, current_date=active_date)
    initial_seen = len(seen)

    unique: list[dict] = []
    batch_urls: set[str] = set()

    for story in stories:
        url = story.get("url", "")
        if not url:
            continue
        norm = normalize_url(url)
        if norm in seen or norm in batch_urls:
            continue
        batch_urls.add(norm)
        unique.append(story)

    dupes_in_batch = len(stories) - len(unique) - (len(stories) - len([s for s in stories if s.get("url")]))
    dupes_cross_run = sum(1 for s in stories if s.get("url") and normalize_url(s["url"]) in seen)

    log.info(
        "dedup complete",
        extra={
            "input": len(stories),
            "unique": len(unique),
            "dupes_in_batch": max(0, dupes_in_batch - dupes_cross_run),
            "dupes_cross_run": dupes_cross_run,
        },
    )

    if persist:
        seen.update(batch_urls)
        _save_seen(seen, path, current_date=active_date)
        log.info("persisted seen URLs", extra={"before": initial_seen, "after": len(seen)})

    return unique
