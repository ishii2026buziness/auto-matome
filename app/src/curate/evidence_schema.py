"""Structured evidence schema for extracted facts from source articles."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class ArticleEvidence:
    """Structured facts extracted from a single source article."""
    title: str
    source: str          # e.g. "HN", "Reddit/r/technology", "Ars Technica"
    url: str
    published: str       # ISO date string
    score: int           # upvotes/HN score
    facts: list[str]     # verified facts (bullet points, no opinions)
    numbers: list[str]   # key numbers/stats e.g. ["30,000 layoffs", "$5B valuation"]
    arguments_for: list[str]   # positive reactions / supporting views
    arguments_against: list[str]  # criticism / opposing views
    public_reaction: str  # summary of community reaction (NOT verbatim quotes)
    predictions: list[str]  # what might happen next (from comments/analysis)


@dataclass
class TopicBrief:
    """Aggregated brief for a topic cluster across multiple sources."""
    topic: str           # inferred topic title
    evidence_list: list[ArticleEvidence] = field(default_factory=list)

    @property
    def all_facts(self) -> list[str]:
        return [f for e in self.evidence_list for f in e.facts]

    @property
    def all_numbers(self) -> list[str]:
        return [n for e in self.evidence_list for n in e.numbers]

    @property
    def source_count(self) -> int:
        return len(self.evidence_list)
