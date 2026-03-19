"""Build structured article briefs from TopicBrief clusters."""
from __future__ import annotations

from dataclasses import dataclass, field

from curate.evidence_schema import TopicBrief


@dataclass
class ArticleBrief:
    """Ready-to-render brief for a single topic cluster."""
    topic: str
    source_count: int
    sources: list[str]          # e.g. ["HackerNews", "Ars Technica"]
    urls: list[tuple[str, str]] # [(title, url), ...]
    what_happened: list[str]    # deduplicated facts
    key_numbers: list[str]      # deduplicated numbers
    pros: list[str]             # arguments for
    cons: list[str]             # arguments against
    public_reaction: str        # combined reaction summary
    predictions: list[str]      # what might happen next
    score_total: int            # sum of scores (for ordering)


def build_briefs(topics: list[TopicBrief]) -> list[ArticleBrief]:
    """Convert TopicBrief list into ArticleBrief list, sorted by score."""
    briefs = [_build_one(t) for t in topics]
    briefs.sort(key=lambda b: b.score_total, reverse=True)
    return briefs


def _build_one(topic: TopicBrief) -> ArticleBrief:
    evs = topic.evidence_list

    # Deduplicate while preserving order
    facts = _dedup([f for e in evs for f in e.facts], limit=5)
    numbers = _dedup([n for e in evs for n in e.numbers], limit=4)
    pros = _dedup([a for e in evs for a in e.arguments_for], limit=3)
    cons = _dedup([a for e in evs for a in e.arguments_against], limit=3)
    predictions = _dedup([p for e in evs for p in e.predictions], limit=3)

    # Combine public reactions (non-empty only)
    reactions = [e.public_reaction for e in evs if e.public_reaction]
    reaction_text = " / ".join(reactions[:3]) if reactions else ""

    urls = [(e.title, e.url) for e in evs if e.url]
    sources = _dedup([e.source for e in evs])
    score_total = sum(e.score for e in evs)

    return ArticleBrief(
        topic=topic.topic,
        source_count=len(evs),
        sources=sources,
        urls=urls,
        what_happened=facts,
        key_numbers=numbers,
        pros=pros,
        cons=cons,
        public_reaction=reaction_text,
        predictions=predictions,
        score_total=score_total,
    )


def _dedup(items: list[str], limit: int = 10) -> list[str]:
    seen: set[str] = set()
    result = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
        if len(result) >= limit:
            break
    return result


def format_briefs_for_prompt(briefs: list[ArticleBrief]) -> str:
    """Serialize ArticleBriefs into a structured text block for Claude."""
    lines = []
    for i, b in enumerate(briefs, 1):
        lines.append(f"### トピック{i}: {b.topic}（{b.source_count}ソース）")
        lines.append(f"- ソース: {', '.join(b.sources)}")
        for title, url in b.urls[:3]:
            lines.append(f"- 元記事: [{title}]({url})")
        if b.what_happened:
            lines.append(f"- 事実: {' / '.join(b.what_happened)}")
        if b.key_numbers:
            lines.append(f"- 数値: {' / '.join(b.key_numbers)}")
        if b.pros:
            lines.append(f"- 肯定意見: {b.pros[0]}")
        if b.cons:
            lines.append(f"- 否定意見: {b.cons[0]}")
        if b.public_reaction:
            lines.append(f"- 世論: {b.public_reaction}")
        if b.predictions:
            lines.append(f"- 予測: {b.predictions[0]}")
        lines.append("")
    return "\n".join(lines)
