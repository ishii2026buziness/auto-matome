"""Extract structured facts from raw story dicts using claude-gateway — batch mode."""
from __future__ import annotations
import asyncio
import json
import os
import re
import urllib.request
from curate.evidence_schema import ArticleEvidence

_GATEWAY_URL = os.environ.get("CLAUDE_GATEWAY_URL", "http://127.0.0.1:18080")


_BATCH_PROMPT = """\
以下の{n}件のニュース記事から、各記事の構造化情報をJSON配列で抽出してください。

{stories_text}

以下のJSON配列形式で出力してください（配列の要素数は入力記事数と同じ{n}件）：
[
  {{
    "facts": ["客観的事実1", "客観的事実2"],
    "numbers": ["重要な数値/統計"],
    "arguments_for": ["肯定的意見の要約"],
    "arguments_against": ["否定的意見の要約"],
    "public_reaction": "コミュニティ反応の独自要約（原文引用なし）",
    "predictions": ["今後の展開予測"]
  }},
  ...
]

ルール:
- factsには客観的事実のみ（意見・推測を含めない）
- public_reactionは原文コメントをそのまま使わず必ず要約
- 全て日本語で出力
- 各リストは最大3件まで
- JSON以外のテキストは出力しない
"""


def _story_to_text(i: int, story: dict, source_label: str) -> str:
    comments = ""
    if story.get("comments"):
        comments = " / ".join(c[:100] for c in story["comments"][:3])
    summary = story.get("summary", story.get("selftext", ""))[:200]
    return (
        f"[{i}] タイトル: {story.get('title', '')}\n"
        f"    ソース: {source_label} | スコア: {story.get('score', story.get('points', 0))}\n"
        f"    概要: {summary}\n"
        f"    コメント: {comments or '（なし）'}"
    )


def _source_label(story: dict) -> str:
    src = story.get("_source", "")
    if src == "hn":
        return "HackerNews"
    if src == "reddit":
        return f"Reddit/r/{story.get('subreddit', '?')}"
    # rss / indieweb: use feed domain or title as label
    feed_url = story.get("source_feed", story.get("feed_url", ""))
    if feed_url:
        from urllib.parse import urlparse
        domain = urlparse(feed_url).netloc.replace("www.", "")
        return domain or src or "RSS"
    return src or "RSS"


async def extract_all_evidence(stories: list[dict]) -> list[ArticleEvidence]:
    """Extract evidence from all stories in a single Claude call."""
    if not stories:
        return []

    labels = [_source_label(s) for s in stories]
    stories_text = "\n\n".join(
        _story_to_text(i + 1, s, labels[i]) for i, s in enumerate(stories)
    )
    prompt = _BATCH_PROMPT.format(n=len(stories), stories_text=stories_text)

    def _call_gateway() -> str:
        payload = json.dumps({"caller": "auto-matome", "provider": "claude", "prompt": prompt}).encode("utf-8")
        request = urllib.request.Request(
            f"{_GATEWAY_URL.rstrip('/')}/v1/generate",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=300) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not result.get("success"):
            raise RuntimeError(result.get("error_message") or "gateway error")
        return result.get("output_text", "")

    raw = await asyncio.to_thread(_call_gateway)

    # Parse JSON array
    try:
        raw = re.sub(r"```(?:json)?\s*\n?", "", raw).strip().rstrip("`").strip()
        data_list = json.loads(raw) if raw else []
        if not isinstance(data_list, list):
            data_list = []
    except (json.JSONDecodeError, ValueError):
        data_list = []

    # Pad with empty dicts if Claude returned fewer items
    while len(data_list) < len(stories):
        data_list.append({})

    results = []
    for story, label, data in zip(stories, labels, data_list):
        results.append(ArticleEvidence(
            title=story.get("title", ""),
            source=label,
            url=story.get("url", ""),
            published=story.get("published", ""),
            score=story.get("score", story.get("points", 0)),
            facts=data.get("facts", []),
            numbers=data.get("numbers", []),
            arguments_for=data.get("arguments_for", []),
            arguments_against=data.get("arguments_against", []),
            public_reaction=data.get("public_reaction", ""),
            predictions=data.get("predictions", []),
        ))
    return results
