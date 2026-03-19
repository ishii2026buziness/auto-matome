"""Auto Matome-specific Heartbeat thresholds.

Thresholds sourced from the execution plan's HEARTBEAT.md section:
- Overseas sources fetched >= 30/day
- Japanese articles published >= 3/day
- Translation quality score >= 0.80 (LLM self-eval)
- Missing source URLs = 0
- Duplicate publication rate <= 5%
- Daily cost <= 3000 JPY
- 7-day rolling PV growth rate: alert if < -15%
- Consecutive API errors: halt after 3
"""

from __future__ import annotations

from common.thresholds import Threshold, Op

# ── Ingestion ──
OVERSEAS_SOURCES_PER_DAY = Threshold(
    name="overseas_sources_per_day",
    op=Op.GTE,
    value=30,
    unit="items",
)

# ── Publication ──
JA_ARTICLES_PER_DAY = Threshold(
    name="ja_articles_per_day",
    op=Op.GTE,
    value=3,
    unit="articles",
)

# ── Translation quality ──
TRANSLATION_QUALITY_SCORE = Threshold(
    name="translation_quality_score",
    op=Op.GTE,
    value=0.80,
    unit="",
)

# ── Source attribution ──
MISSING_SOURCE_URLS = Threshold(
    name="missing_source_urls",
    op=Op.EQ,
    value=0,
    unit="items",
)

# ── Deduplication ──
DUPLICATE_PUBLICATION_RATE = Threshold(
    name="duplicate_publication_rate",
    op=Op.LTE,
    value=5.0,
    unit="%",
)

# ── Budget ──
DAILY_COST_JPY = Threshold(
    name="daily_cost_jpy",
    op=Op.LTE,
    value=3000,
    unit="JPY",
)

# ── Growth ──
PV_GROWTH_7D = Threshold(
    name="pv_growth_7d",
    op=Op.GTE,
    value=-15.0,
    unit="%",
)

# ── Reliability ──
CONSECUTIVE_API_ERRORS = Threshold(
    name="consecutive_api_errors",
    op=Op.LT,
    value=3,
    unit="errors",
)

# Convenience list of all thresholds for batch checking.
ALL_THRESHOLDS = [
    OVERSEAS_SOURCES_PER_DAY,
    JA_ARTICLES_PER_DAY,
    TRANSLATION_QUALITY_SCORE,
    MISSING_SOURCE_URLS,
    DUPLICATE_PUBLICATION_RATE,
    DAILY_COST_JPY,
    PV_GROWTH_7D,
    CONSECUTIVE_API_ERRORS,
]
