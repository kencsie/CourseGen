"""Tests for the preset study-time estimation helpers."""
from coursegen.ui.utils.study_estimate import (
    estimate_study_minutes,
    format_duration_range,
    node_study_minutes,
)

# ── per-node, type + item counts ──────────────────────────────────────────

def test_concept_counts_points_and_examples():
    content = {"key_points": ["a", "b", "c", "d"], "examples": ["x", "y"]}
    assert node_study_minutes("concept", content) == 20 + 20 + 16  # 56


def test_practice_counts_tasks():
    assert node_study_minutes("practice", {"tasks": [1, 2, 3]}) == 65


def test_comparison_counts_rows():
    assert node_study_minutes("comparison", {"comparison_table": [1, 2, 3, 4]}) == 24


def test_pitfall_counts_pitfalls_and_signs():
    content = {"pitfalls": [1, 2, 3, 4], "warning_signs": [1, 2]}
    assert node_study_minutes("pitfall", content) == 10 + 16 + 4  # 30


def test_prerequisite_counts_remediation():
    assert node_study_minutes("prerequisite", {"remediation": [1, 2]}) == 25


# ── fallbacks & robustness ────────────────────────────────────────────────

def test_missing_content_falls_back_to_base():
    assert node_study_minutes("concept", None) == 20
    assert node_study_minutes("practice", {}) == 20


def test_unknown_type_fallback():
    assert node_study_minutes("mystery", {"foo": [1, 2]}) == 30


def test_null_list_fields_are_tolerated():
    assert node_study_minutes("concept", {"key_points": None, "examples": None}) == 20


# ── roadmap-level sum ─────────────────────────────────────────────────────

def test_estimate_sums_nodes_with_content_map():
    nodes = [
        {"id": "1", "type": "concept"},
        {"id": "2", "type": "practice"},
        {"id": "3", "type": "comparison"},  # no content entry -> base 12
    ]
    content_map = {
        "1": {"key_points": [1, 2, 3, 4], "examples": [1, 2]},  # 56
        "2": {"tasks": [1, 2, 3]},                               # 65
    }
    assert estimate_study_minutes(nodes, content_map) == 56 + 65 + 12  # 133


# ── range formatting (×0.8 ~ ×1.2 band) ──────────────────────────────────

def test_format_range_uses_080_to_120_band():
    # 406 min -> 0.8x = 324.8 (~5.5h), 1.2x = 487.2 (~8h)
    assert format_duration_range(406) == "約 5.5–8 小時"


def test_format_range_handles_tiny_totals():
    assert format_duration_range(10).startswith("約 0.5")
