from __future__ import annotations

import asyncio

import pytest

from src.curate.matome_converter import GatewayClient, _build_story_digest, has_meaningful_body



def test_has_meaningful_body_rejects_placeholder_only_output():
    markdown = """\
---
date: 2026-03-15
title: 海外テックまとめ 2026-03-15
description: test
---

## 本日の記事一覧
"""
    assert has_meaningful_body(markdown) is False


def test_has_meaningful_body_accepts_article_content():
    markdown = """\
---
date: 2026-03-15
title: 海外テックまとめ 2026-03-15
description: test
---

## 【速報】AI新機能が出た件

> 概要: これは要約です

1 名無しさん
これは本文
"""
    assert has_meaningful_body(markdown) is True


def test_build_story_digest_includes_summary_and_url():
    digest = _build_story_digest(
        [
            {
                "title": "Test Story",
                "url": "https://example.com/story",
                "summary": "This is a short summary for the story.",
            }
        ]
    )
    assert "## Test Story" in digest
    assert "> 概要: This is a short summary for the story." in digest
    assert "元記事: https://example.com/story" in digest


@pytest.mark.asyncio
async def test_gateway_client_calls_generate_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    import json as _json

    def fake_call_sync(self, prompt: str) -> str:
        assert prompt == "hello"
        return "## test"

    monkeypatch.setattr(GatewayClient, "_call_sync", fake_call_sync)

    result = await GatewayClient().run("hello")
    assert result == "## test"


@pytest.mark.asyncio
async def test_gateway_client_raises_on_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_call_sync(self, prompt: str) -> str:
        raise RuntimeError("gateway error")

    monkeypatch.setattr(GatewayClient, "_call_sync", fake_call_sync)

    with pytest.raises(RuntimeError, match="gateway error"):
        await GatewayClient().run("hello")
