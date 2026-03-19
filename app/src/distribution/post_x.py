"""Post curated article links and summaries to X (Twitter).

Formats a tweet with the Japanese title, a brief summary, tags,
and the source URL. Respects rate limits and daily posting caps.
"""

from __future__ import annotations

import httpx

from common.config import load_config


def post(article: dict) -> dict:
    """Post an article summary to X.

    Args:
        article: Curated article dict with title, summary, url, tags.

    Returns:
        Dict with keys: tweet_id, posted_at, success.

    Raises:
        NotImplementedError: Stub — not yet implemented.
    """
    raise NotImplementedError("post_x.post is not yet implemented")
