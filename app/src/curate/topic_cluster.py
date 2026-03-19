"""Cluster ArticleEvidence into TopicBrief groups using claude-gateway."""
from __future__ import annotations

import asyncio
import json
import os
import re
import urllib.request

from curate.evidence_schema import ArticleEvidence, TopicBrief

_GATEWAY_URL = os.environ.get("CLAUDE_GATEWAY_URL", "http://127.0.0.1:18080")


_CLUSTER_PROMPT = """\
以下の{n}件の記事evidenceを、共通のトピック・テーマでグループ化してください。

{items}

ルール:
- 同じ出来事・製品・トレンドを扱う記事は同じグループにまとめる
- 無関係な記事は別グループ（1件だけのグループも可）
- グループ数は{min_g}〜{max_g}個が目安
- topic_titleは日本語で20文字以内、記事内容を象徴する見出し

以下のJSON形式で出力（JSON以外は出力しない）:
[
  {{
    "topic_title": "グループのテーマ名",
    "indices": [0, 2, 5]
  }},
  ...
]
"""


async def cluster_by_topic(
    evidence_list: list[ArticleEvidence],
    min_groups: int = 3,
    max_groups: int = 8,
) -> list[TopicBrief]:
    """Group evidence into topic clusters via Claude."""
    if not evidence_list:
        return []

    # If too few articles, skip clustering — one group per article
    if len(evidence_list) <= 3:
        return [
            TopicBrief(topic=e.title[:40], evidence_list=[e])
            for e in evidence_list
        ]

    items_text = "\n\n".join(
        f"[{i}] {e.title}\n    ソース: {e.source} | 事実: {'; '.join(e.facts[:2])}"
        for i, e in enumerate(evidence_list)
    )
    prompt = _CLUSTER_PROMPT.format(
        n=len(evidence_list),
        items=items_text,
        min_g=min_groups,
        max_g=min(max_groups, len(evidence_list)),
    )

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

    clusters = _parse_clusters(raw, evidence_list)

    # Fallback: if parsing failed, one cluster per article
    if not clusters:
        return [
            TopicBrief(topic=e.title[:40], evidence_list=[e])
            for e in evidence_list
        ]

    return clusters


def _parse_clusters(raw: str, evidence_list: list[ArticleEvidence]) -> list[TopicBrief]:
    try:
        raw = re.sub(r"```(?:json)?\s*\n?", "", raw).strip().rstrip("`").strip()
        data = json.loads(raw)
        if not isinstance(data, list):
            return []
    except (json.JSONDecodeError, ValueError):
        return []

    assigned = set()
    topics: list[TopicBrief] = []

    for item in data:
        title = item.get("topic_title", "")
        indices = [i for i in item.get("indices", []) if isinstance(i, int) and 0 <= i < len(evidence_list)]
        if not indices:
            continue
        evs = [evidence_list[i] for i in indices]
        topics.append(TopicBrief(topic=title, evidence_list=evs))
        assigned.update(indices)

    # Any evidence not assigned gets its own single-article topic
    for i, ev in enumerate(evidence_list):
        if i not in assigned:
            topics.append(TopicBrief(topic=ev.title[:40], evidence_list=[ev]))

    return topics
