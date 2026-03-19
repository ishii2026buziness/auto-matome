"""Tests for Auto Matome pipeline configuration."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import patch

import pytest

from common.config import PipelineConfig

# We import indirectly to avoid needing all env vars set.
# The AutoMatomeConfig is tested by constructing it with explicit values.


def test_auto_matome_config_defaults():
    """AutoMatomeConfig can be instantiated with defaults."""
    # Import here to avoid module-level env var issues.
    from src.common.config import AutoMatomeConfig

    config = AutoMatomeConfig(
        pipeline_name="auto_matome",
        _env_file=None,  # skip .env loading in tests
    )
    assert config.pipeline_name == "auto_matome"
    assert config.daily_budget_jpy == 5000
    assert config.translation_provider == "gemini"
    assert config.dry_run is True
    assert config.reddit_client_id == ""
    assert config.translation_budget_jpy == 2000
    assert config.hn_api_base == "https://hacker-news.firebaseio.com/v0"


def test_auto_matome_config_extends_pipeline_config():
    """AutoMatomeConfig is a subclass of PipelineConfig."""
    from src.common.config import AutoMatomeConfig

    assert issubclass(AutoMatomeConfig, PipelineConfig)


def test_auto_matome_config_with_overrides():
    """AutoMatomeConfig respects explicit field values."""
    from src.common.config import AutoMatomeConfig

    config = AutoMatomeConfig(
        pipeline_name="auto_matome",
        reddit_client_id="test_client_id",
        translation_provider="gemini",
        daily_budget_jpy=3000,
        translation_budget_jpy=1500,
        zenn_username="testuser",
        dry_run=False,
        _env_file=None,
    )
    assert config.reddit_client_id == "test_client_id"
    assert config.translation_provider == "gemini"
    assert config.daily_budget_jpy == 3000
    assert config.translation_budget_jpy == 1500
    assert config.zenn_username == "testuser"
    assert config.dry_run is False


def test_get_config_helper():
    """get_config() returns a AutoMatomeConfig instance."""
    from src.common.config import get_config, AutoMatomeConfig

    config = get_config(
        pipeline_name="auto_matome",
        _env_file=None,
    )
    assert isinstance(config, AutoMatomeConfig)
    assert config.pipeline_name == "auto_matome"
