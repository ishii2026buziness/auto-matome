"""2ch-style matome converter — NotebookLM multi-turn → per-topic Claude recompose.

Pipeline:
  stories → NotebookLM(topic list → per-topic deep-dive) → Claude per topic → combined output
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import urllib.request
from datetime import date

from curate.notebooklm_synthesizer import TopicInsight


_GATEWAY_URL = os.environ.get("CLAUDE_GATEWAY_URL", "http://127.0.0.1:18080")


_ARTICLE_PROMPT = """\
あなたは日本語の2chまとめサイトの編集者です。
以下の「トピック分析」をもとに、2ch風まとめ記事を1本書いてください。

## ルール
- 元記事の文章表現は一切使わない
- 画像・iframe埋め込み禁止
- 名無しのレスは「反応」だけ。説明・解説は概要欄に書く

## フォーマット
```
## 【タグ】〜〜な件

> 概要: 何が起きたか・なぜ話題か・数値を2〜3行（事実のみ）

{source_links}

スレの反応

1 名無しさん
（感想・ツッコミ・煽り）

2 名無しさん
（別角度の反応）

3 名無しさん
（皮肉・笑い・意外な視点）

4 名無しさん
（「それってつまり〜？」的な一言）
```

## スレタイルール
- 【悲報】【朗報】【速報】【衝撃】【草】等
- 煽り気味、でも情報は正確に
- 「→結果wwww」「〜な件wwwww」構造を使う

---

## トピック: {topic}

{insights}

---

記事本文だけ出力してください（frontmatterなし）。
"""

_DAILY_FRONTMATTER = """\
---
date: {today}
title: 海外テックまとめ {today}
description: 複数ソースのAI・テックニュースを独自解釈でまとめました
---

"""


def has_meaningful_body(markdown: str) -> bool:
    """Return True when the markdown body contains more than headings/placeholders."""
    if not markdown.strip():
        return False

    body = markdown
    if body.startswith("---\n"):
        end = body.find("\n---\n", 4)
        if end != -1:
            body = body[end + 5 :]

    content_lines = []
    for raw_line in body.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line == "## 本日の記事一覧":
            continue
        if line.startswith("---"):
            continue
        content_lines.append(line)

    return bool(content_lines)


def _build_story_digest(stories: list[dict]) -> str:
    sections = []
    for story in stories[:10]:
        title = (story.get("title") or "無題").strip()
        url = (story.get("url") or "").strip()
        summary = (story.get("description") or story.get("summary") or "").strip()
        summary = re.sub(r"\s+", " ", summary)[:180]

        lines = [f"## {title}"]
        if summary:
            lines.append(f"> 概要: {summary}")
        if url:
            lines.append(f"元記事: {url}")
        sections.append("\n\n".join(lines))

    if not sections:
        return "## 本日の記事一覧\n\nソース更新はありましたが、本文を生成できませんでした。"

    return "\n\n---\n\n".join(sections)


def _make_source_links(topic: TopicInsight) -> str:
    if not topic.source_urls:
        return ""
    lines = []
    for i, url in enumerate(topic.source_urls[:5]):
        title = topic.source_titles[i] if i < len(topic.source_titles) else url
        title = title[:60] or url
        lines.append(f"元記事: [{title}]({url})")
    return "\n".join(lines)


def _strip_fences(text: str) -> str:
    text = re.sub(r"```(?:markdown)?\s*\n?", "", text)
    text = re.sub(r"\n```\s*$", "", text.strip())
    text = re.sub(r"(?m)^>>(\d+)", r"＞＞\1", text)
    return text.strip()


class GatewayClient:
    def __init__(self, gateway_url: str | None = None) -> None:
        self.gateway_url = (gateway_url or _GATEWAY_URL).rstrip("/")

    def _call_sync(self, prompt: str) -> str:
        payload = json.dumps({
            "caller": "auto-matome",
            "provider": "claude",
            "prompt": prompt,
        }).encode("utf-8")
        request = urllib.request.Request(
            f"{self.gateway_url}/v1/generate",
            data=payload,
            method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(request, timeout=300) as response:
            result = json.loads(response.read().decode("utf-8"))
        if not result.get("success"):
            raise RuntimeError(result.get("error_message") or "gateway error")
        return _strip_fences(result.get("output_text", ""))

    async def run(self, prompt: str) -> str:
        return await asyncio.to_thread(self._call_sync, prompt)


async def _write_one_article(topic: TopicInsight) -> str:
    """One Claude call per topic → one article string."""
    source_links = _make_source_links(topic)
    prompt = _ARTICLE_PROMPT.format(
        topic=topic.title,
        insights=topic.insights,
        source_links=source_links,
    )
    return await GatewayClient().run(prompt)


async def convert_to_matome(
    hn_stories: list[dict],
    indieweb_stories: list[dict],
    reddit_stories: list[dict] | None = None,
    *,
    run_date: date | None = None,
) -> str:
    """Full pipeline: NotebookLM multi-turn → parallel Claude writes → combined markdown."""
    from curate.notebooklm_synthesizer import analyze_with_notebooklm, cleanup_notebook

    rd = reddit_stories or []
    all_stories = hn_stories[:10] + indieweb_stories[:15] + rd[:8]

    # Step 1: NotebookLM multi-turn analysis (topic list → per-topic deep-dive)
    active_date = run_date or date.today()
    analysis = await analyze_with_notebooklm(all_stories, run_date=active_date)

    if not analysis or not analysis.topics:
        # Fallback: Claude直接呼び出しで2ch風コンテンツを生成
        try:
            return await _fallback_output(all_stories)
        except Exception as e:
            # Claude呼び出し失敗時は最終手段のタイトル列挙
            today = active_date.isoformat()
            return (
                f"---\ndate: {today}\ntitle: 海外テックまとめ {today}\n"
                f"description: 複数ソースのAI・テックニュースを独自解釈でまとめました\n---\n\n"
                f"{_build_story_digest(all_stories)}\n"
            )

    # Step 2: Write one article per topic in parallel
    article_tasks = [_write_one_article(t) for t in analysis.topics]
    articles = await asyncio.gather(*article_tasks)

    # Cleanup
    cleanup_notebook(analysis.notebook_id)

    today = active_date.isoformat()
    body = "\n\n---\n\n".join(a for a in articles if a.strip())
    return _DAILY_FRONTMATTER.format(today=today) + body


_FALLBACK_PROMPT = """\
あなたは日本語の2chまとめサイトの編集者です。
以下の海外テックニュース一覧をもとに、2ch風まとめ記事を複数本書いてください。

## ルール
- 元記事の文章表現は一切使わない
- 名無しのレスは「反応」だけ。説明・解説は概要欄に書く

## フォーマット（記事ごとに繰り返す）
```
## 【タグ】〜〜な件

> 概要: 何が起きたか・なぜ話題か（2〜3行）

元記事: [タイトル](URL)

スレの反応

1 名無しさん
（感想・ツッコミ・煽り）

2 名無しさん
（別角度の反応）

3 名無しさん
（皮肉・笑い・意外な視点）
```

## スレタイルール
- 【悲報】【朗報】【速報】【衝撃】【草】等
- 「→結果wwww」「〜な件wwwww」構造

---

## ニュース一覧

{stories_text}

---

記事本文だけ出力してください（frontmatterなし）。3〜5本書いてください。
"""


async def _fallback_output(stories: list[dict], *, run_date: date | None = None) -> str:
    """Claude直接呼び出しで2ch風コンテンツを生成（NotebookLM失敗時）。"""
    today = (run_date or date.today()).isoformat()
    lines = []
    for s in stories[:15]:
        title = s.get("title", "")
        url = s.get("url", "")
        desc = s.get("description") or s.get("summary") or ""
        if desc:
            lines.append(f"- [{title}]({url})\n  {desc[:120]}")
        else:
            lines.append(f"- [{title}]({url})")
    stories_text = "\n".join(lines)

    prompt = _FALLBACK_PROMPT.format(stories_text=stories_text)
    body = await GatewayClient().run(prompt)
    if not body:
        body = _build_story_digest(stories)

    frontmatter = (
        f"---\ndate: {today}\ntitle: 海外テックまとめ {today}\n"
        f"description: 複数ソースのAI・テックニュースを独自解釈でまとめました\n---\n\n"
    )
    return frontmatter + body
