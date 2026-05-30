"""Heuristic, preset study-time estimation for a roadmap.

Deliberately approximate — the sidebar discloses it as a preset-parameter
estimate. Base minutes reflect each node type's learning ACTIVITY
(practice > concept > comparison/pitfall > prerequisite); per-item bonuses
scale with the actual generated content so thin and rich nodes differ.
"""
from __future__ import annotations

# Fast/slow band applied to the point estimate to produce the displayed range.
_FAST_FACTOR = 0.8
_SLOW_FACTOR = 1.2


def node_study_minutes(node_type: str, content: dict | None) -> int:
    """Estimate study minutes for one node from its type + content shape."""
    c = content or {}
    if node_type == "concept":
        return (
            20
            + 5 * len(c.get("key_points") or [])
            + 8 * len(c.get("examples") or [])
        )
    if node_type == "practice":
        return 20 + 15 * len(c.get("tasks") or [])
    if node_type == "comparison":
        return 12 + 3 * len(c.get("comparison_table") or [])
    if node_type == "pitfall":
        return (
            10
            + 4 * len(c.get("pitfalls") or [])
            + 2 * len(c.get("warning_signs") or [])
        )
    if node_type == "prerequisite":
        return 15 + 5 * len(c.get("remediation") or [])
    return 30  # unknown type — conservative fallback


def estimate_study_minutes(nodes: list[dict], content_map: dict) -> int:
    """Sum the per-node study-time estimate across a roadmap."""
    return sum(
        node_study_minutes(n.get("type"), content_map.get(n.get("id")))
        for n in nodes
    )


def _round_half_hour(minutes: float) -> float:
    """Round minutes to the nearest half hour, expressed in hours."""
    return round(minutes / 30) / 2


def format_duration_range(minutes: int) -> str:
    """Render a point estimate as a friendly hour range (×0.8–×1.2)."""
    low = max(0.5, _round_half_hour(minutes * _FAST_FACTOR))
    high = _round_half_hour(minutes * _SLOW_FACTOR)
    if high <= low:
        high = low + 0.5
    return f"約 {low:g}–{high:g} 小時"
