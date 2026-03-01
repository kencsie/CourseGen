"""Pydantic models for evaluation results."""
from __future__ import annotations

from pydantic import BaseModel, Field


# ── Layer 1: Pipeline Metrics ──


class PipelineMetrics(BaseModel):
    """Aggregate statistics across all evaluated generation records."""

    total_generations: int
    roadmap_first_pass_rate: float = Field(description="Fraction of roadmaps accepted on first iteration")
    avg_roadmap_iterations: float
    content_success_rate: float = Field(description="1 - (total failed nodes / total nodes)")
    avg_failed_nodes_per_gen: float
    avg_generation_time_sec: float
    avg_total_tokens: float
    avg_cost_usd: float
    node_type_distribution: dict[str, int] = Field(description="Count of each node type across all roadmaps")


# ── Layer 2: Structural Checks ──


class CheckFailure(BaseModel):
    """A single structural check failure."""

    node_id: str | None = Field(default=None, description="None for roadmap-level failures")
    check: str
    detail: str


class StructuralReport(BaseModel):
    """Per-generation structural check report."""

    generation_id: str
    topic: str
    passed: bool
    total_checks: int
    failures: list[CheckFailure]


# ── Layer 3: LLM Judge ──


class JudgeDimension(BaseModel):
    reason: str
    score: int


class JudgeResult(BaseModel):
    accuracy: JudgeDimension
    completeness: JudgeDimension
    structure: JudgeDimension
    practicality: JudgeDimension
    citation: JudgeDimension


class ModelScore(BaseModel):
    """One judge model's scores for one generation."""

    model_name: str
    result: JudgeResult


class DimensionAggregate(BaseModel):
    """Per-dimension aggregated score across judges."""

    mean: float
    std: float
    scores: list[float]


class MultiJudgeResult(BaseModel):
    """Aggregated result from multiple judge models for one generation."""

    generation_id: str
    topic: str
    model_scores: list[ModelScore]
    aggregate: dict[str, DimensionAggregate] = Field(
        description="Keyed by dimension name: accuracy, completeness, etc."
    )
    overall_mean: float
    overall_std: float


# ── Full Eval Result ──


class EvalResult(BaseModel):
    """Complete evaluation output saved to JSON."""

    pipeline_metrics: PipelineMetrics
    structural_reports: list[StructuralReport]
    structural_pass_rate: float
    judge_results: list[MultiJudgeResult] | None = None
