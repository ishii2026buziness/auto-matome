"""Generate engagement reports combining traffic and social metrics.

Merges Plausible traffic data with X engagement metrics (likes,
retweets, replies) and Zenn view counts to produce a unified
daily/weekly engagement report used by the orchestrator to
adjust topic weighting.
"""

from __future__ import annotations

from common.metrics import MetricsCollector


def generate_report(*, days: int = 7) -> dict:
    """Generate an engagement report for the given period.

    Args:
        days: Number of days to cover in the report.

    Returns:
        Dict with keys: period, total_pageviews, pv_growth_pct,
        top_articles (list), social_engagement (dict), recommendations (list).

    Raises:
        NotImplementedError: Stub — not yet implemented.
    """
    raise NotImplementedError("engagement_report.generate_report is not yet implemented")
