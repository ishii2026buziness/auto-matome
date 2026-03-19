"""Fetch posts from X (Twitter) via the X API v2.

Searches for tweets matching curated keywords and lists related
to web revival, indie web, and personal websites. Requires X API
credentials (OAuth 1.0a or Bearer token) in config.
"""

from __future__ import annotations

import httpx

from common.config import load_config


def fetch() -> list[dict]:
    """Fetch recent tweets matching configured search terms.

    Returns:
        List of dicts with at least: title, url, source, published, raw_content.

    Raises:
        NotImplementedError: Stub — not yet implemented.
    """
    raise NotImplementedError("fetch_x.fetch is not yet implemented")
