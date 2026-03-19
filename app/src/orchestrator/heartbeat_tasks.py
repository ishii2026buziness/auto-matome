"""Legacy threshold-check helpers for Auto Matome.

These stubs are not a scheduler and must not grow into a custom operational
control plane. Runtime scheduling belongs to systemd/Quadlet, and monitoring
should flow through structured job results plus Prometheus metrics.
"""

from __future__ import annotations

from common.thresholds import check_all


def run_heartbeat() -> dict:
    """Execute threshold checks and return a summary.

    Returns:
        Dict with keys: all_passed (bool), checks (list of result dicts),
        actions_triggered (list of follow-up recommendations).

    Raises:
        NotImplementedError: Stub — not yet implemented.
    """
    raise NotImplementedError("heartbeat_tasks.run_heartbeat is not yet implemented")


def rebalance_topics(engagement_report: dict) -> dict:
    """Suggest topic-weight changes based on engagement data.

    This is an analysis helper only. It must not directly implement
    scheduling, retries, or service control.

    Args:
        engagement_report: Output from analytics.engagement_report.generate_report.

    Returns:
        Dict with old_weights, new_weights, reason.

    Raises:
        NotImplementedError: Stub — not yet implemented.
    """
    raise NotImplementedError("heartbeat_tasks.rebalance_topics is not yet implemented")
