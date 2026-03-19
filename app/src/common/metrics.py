"""Pipeline-specific metrics setup for Auto Matome.

Instantiates a MetricsCollector from the shared common package,
pre-configured with pipeline='auto_matome'.
"""

from __future__ import annotations

from common.metrics import MetricsCollector

# Singleton collector for the auto_matome pipeline.
# Import this from any module that needs to record metrics.
collector = MetricsCollector(pipeline="auto_matome")
