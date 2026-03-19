"""Pull traffic analytics from Plausible (or GA4).

Fetches page-view counts, unique visitors, referrer breakdowns,
and per-article performance for the curation site.
"""

from __future__ import annotations

import httpx

from common.config import load_config


def pull(*, days: int = 7) -> dict:
    """Pull traffic data for the configured site.

    Args:
        days: Number of days of data to retrieve.

    Returns:
        Dict with keys: total_pageviews, unique_visitors,
        top_pages (list), referrers (list), period.

    Raises:
        NotImplementedError: Stub — not yet implemented.
    """
    raise NotImplementedError("traffic_pull.pull is not yet implemented")
