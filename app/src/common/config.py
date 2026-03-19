"""Auto Matome pipeline configuration, extending shared PipelineConfig."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field
from common.config import PipelineConfig, load_config


class AutoMatomeConfig(PipelineConfig):
    """Configuration for the Auto Matome pipeline.

    Extends the shared PipelineConfig with fields specific to
    content ingestion, translation, publishing, and analytics.
    """

    pipeline_name: str = Field(default="auto_matome")

    # Reddit API credentials
    reddit_client_id: str = Field(default="", description="Reddit OAuth app client ID")
    reddit_client_secret: str = Field(default="", description="Reddit OAuth app client secret")
    reddit_username: str = Field(default="", description="Reddit account username")
    reddit_password: str = Field(default="", description="Reddit account password")

    # X (Twitter) API credentials
    x_api_key: str = Field(default="", description="X API consumer key")
    x_api_secret: str = Field(default="", description="X API consumer secret")
    x_access_token: str = Field(default="", description="X API access token")
    x_access_token_secret: str = Field(default="", description="X API access token secret")

    # Hacker News
    hn_api_base: str = Field(
        default="https://hacker-news.firebaseio.com/v0",
        description="HN Firebase API base URL",
    )

    # IndieWeb / RSS
    indieweb_opml_path: str = Field(default="feeds.opml", description="Path to OPML feed list")
    indieweb_feed_urls: str = Field(default="", description="Comma-separated RSS/Atom feed URLs")

    # Translation / LLM
    translation_provider: Literal["gemini"] = Field(
        default="gemini",
        description="Which LLM provider to use for translation",
    )
    gemini_api_key: str = Field(default="", description="Google Gemini API key")

    # Zenn publishing
    zenn_username: str = Field(default="", description="Zenn account username")
    zenn_repo_path: str = Field(default="", description="Local path to Zenn content repo")

    # Analytics
    plausible_site_id: str = Field(default="", description="Plausible analytics site ID")
    plausible_api_key: str = Field(default="", description="Plausible analytics API key")

    # Budget sub-limits
    translation_budget_jpy: int = Field(
        default=2000,
        description="Max daily translation API spend in JPY",
    )

    model_config = {"env_prefix": "AM_", "env_file": ".env", "extra": "ignore"}


def get_config(**overrides) -> AutoMatomeConfig:
    """Load AutoMatomeConfig from environment / .env file."""
    return load_config(AutoMatomeConfig, **overrides)
