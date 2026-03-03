"""Layer 1: Pipeline health metrics from DB generation records."""
from __future__ import annotations

from collections import Counter

from coursegen.eval.schemas import PipelineMetrics


def compute_pipeline_metrics(generations: list[dict]) -> PipelineMetrics:
    """Aggregate pipeline-level statistics. No LLM calls needed.

    Args:
        generations: list of dicts from ``load_generation()``.
    """
    n = len(generations)
    if n == 0:
        return PipelineMetrics(
            total_generations=0,
            roadmap_first_pass_rate=0.0,
            avg_roadmap_iterations=0.0,
            content_success_rate=0.0,
            avg_failed_nodes_per_gen=0.0,
            avg_generation_time_sec=0.0,
            avg_total_tokens=0.0,
            avg_cost_usd=0.0,
            node_type_distribution={},
        )

    first_pass = sum(1 for g in generations if (g.get("iteration_count") or 1) == 1)
    avg_iter = _avg([g.get("iteration_count") or 1 for g in generations])

    # Content success rate
    total_nodes = 0
    total_failed = 0
    for g in generations:
        nodes = g.get("roadmap", {}).get("nodes", [])
        total_nodes += len(nodes)
        total_failed += len(g.get("content_failed_nodes") or [])
    content_success = 1 - (total_failed / total_nodes) if total_nodes else 1.0

    avg_failed = _avg([len(g.get("content_failed_nodes") or []) for g in generations])
    avg_time = _avg([g.get("generation_time_sec") or 0 for g in generations])
    avg_tokens = _avg([g.get("total_tokens") or 0 for g in generations])
    avg_cost = _avg([g.get("total_cost_usd") or 0 for g in generations])

    # Cleaning stats
    gens_with_cleaning = [
        g for g in generations
        if g.get("raw_content_chars") and g["raw_content_chars"] > 0
    ]
    avg_raw = _avg([g["raw_content_chars"] for g in gens_with_cleaning])
    avg_cleaned = _avg([g["cleaned_content_chars"] or 0 for g in gens_with_cleaning])
    reduction_pcts = [
        (1 - (g.get("cleaned_content_chars") or 0) / g["raw_content_chars"]) * 100
        for g in gens_with_cleaning
    ]
    avg_reduction = _avg(reduction_pcts)

    # Node type distribution
    type_counter: Counter[str] = Counter()
    for g in generations:
        for node in g.get("roadmap", {}).get("nodes", []):
            type_counter[node.get("type", "unknown")] += 1

    return PipelineMetrics(
        total_generations=n,
        roadmap_first_pass_rate=first_pass / n,
        avg_roadmap_iterations=avg_iter,
        content_success_rate=content_success,
        avg_failed_nodes_per_gen=avg_failed,
        avg_generation_time_sec=avg_time,
        avg_total_tokens=avg_tokens,
        avg_cost_usd=avg_cost,
        avg_raw_content_chars=avg_raw,
        avg_cleaned_content_chars=avg_cleaned,
        avg_cleaning_reduction_pct=avg_reduction,
        node_type_distribution=dict(type_counter),
    )


def _avg(values: list[float | int]) -> float:
    return sum(values) / len(values) if values else 0.0
