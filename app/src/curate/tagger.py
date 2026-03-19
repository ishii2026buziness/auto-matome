"""Auto-tag articles with topic labels.

Uses keyword extraction and/or LLM classification to assign
topic tags (e.g. 'indieweb', 'css', 'webperf', 'accessibility')
to each curated article for filtering and trend analysis.
"""

from __future__ import annotations


def tag(article: dict) -> dict:
    """Assign topic tags to an article.

    Args:
        article: Dict containing at minimum title, summary, and translated_text.

    Returns:
        The article dict enriched with a 'tags' list of strings.

    Raises:
        NotImplementedError: Stub — not yet implemented.
    """
    raise NotImplementedError("tagger.tag is not yet implemented")
