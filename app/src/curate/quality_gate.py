"""Quality gate for curated articles before publication.

Extends the shared QualityGate base class to enforce Auto Matome-specific
checks: title quality, URL presence, and content signals.
"""

from __future__ import annotations

from typing import Any

from common.quality_gate import QualityGate
from common.thresholds import Threshold, Op


class AutoMatomeQualityGate(QualityGate):
    """Quality gate for Auto Matome articles.

    Checks:
    - Title length >= 5 characters (reject garbage/empty titles)
    - Title length <= 200 characters (reject spam/concatenated titles)
    - URL length >= 10 characters (must have a real URL)
    - Score >= 0 (for scored sources like HN; always passes for IndieWeb)
    """

    def define_checks(self, item: Any) -> list[tuple[Threshold, float]]:
        title = item.get("title", "")
        url = item.get("url", "")
        score = item.get("score", 0)

        return [
            (Threshold("title_length", Op.GTE, 5), len(title)),
            (Threshold("title_length", Op.LTE, 200), len(title)),
            (Threshold("url_length", Op.GTE, 10), len(url)),
            (Threshold("score", Op.GTE, 0), score),
        ]
