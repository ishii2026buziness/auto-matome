"""Publish curated articles to Zenn as markdown articles.

Generates Zenn-compatible markdown with frontmatter, writes it to
the configured Zenn content repo, and triggers a git push to
publish via Zenn's GitHub integration.
"""

from __future__ import annotations

from pathlib import Path

from common.config import load_config


def post(article: dict) -> dict:
    """Publish an article to Zenn.

    Args:
        article: Curated article dict with title, translated_text, summary, tags.

    Returns:
        Dict with keys: slug, file_path, success.

    Raises:
        NotImplementedError: Stub — not yet implemented.
    """
    raise NotImplementedError("post_zenn.post is not yet implemented")
