"""Summarise articles into concise Japanese abstracts.

Generates a short summary suitable for the curation site and
social media distribution. Summaries are produced via LLM after
translation, ensuring the output is in natural Japanese.
"""

from __future__ import annotations

import httpx

from common.budget import BudgetTracker


def summarize(article: dict) -> dict:
    """Generate a Japanese summary for a translated article.

    Args:
        article: Dict containing at minimum translated_text and title.

    Returns:
        The article dict enriched with 'summary' and 'summary_cost_jpy'.

    Raises:
        NotImplementedError: Stub — not yet implemented.
    """
    raise NotImplementedError("summarize.summarize is not yet implemented")
