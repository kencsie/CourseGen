"""CLI entry point: run all 3 evaluation layers and output summary.

Usage:
    python -m coursegen.eval.run_eval                   # all generations
    python -m coursegen.eval.run_eval --id <record_id>  # single generation
    python -m coursegen.eval.run_eval --no-llm-judge     # Layer 1+2 only
    python -m coursegen.eval.run_eval --list             # list all record IDs
"""
from __future__ import annotations

import argparse
import json
import statistics
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from coursegen.db.crud import list_generations, load_generation
from coursegen.eval.llm_judge import DIMENSIONS, judge_multi
from coursegen.eval.pipeline_metrics import compute_pipeline_metrics
from coursegen.eval.schemas import EvalResult, MultiJudgeResult, StructuralReport
from coursegen.eval.structural_checks import run_structural_checks


def _load_all_generations(record_id: str | None = None) -> list[dict]:
    """Load full generation records from DB."""
    if record_id:
        gen = load_generation(record_id)
        if gen is None:
            print(f"Error: record '{record_id}' not found.")
            raise SystemExit(1)
        return [gen]

    summaries = list_generations(limit=200)
    if not summaries:
        print("No generation records found in DB.")
        raise SystemExit(1)

    generations = []
    for s in summaries:
        gen = load_generation(s["id"])
        if gen:
            generations.append(gen)
    return generations


# ── Pretty printers ──


def _print_pipeline_metrics(metrics) -> None:
    print(f"\n{'='*50}")
    print(f"  Pipeline Metrics (N={metrics.total_generations})")
    print(f"{'='*50}")
    print(f"  Roadmap first-pass rate:  {metrics.roadmap_first_pass_rate:.1%}")
    print(f"  Avg roadmap iterations:   {metrics.avg_roadmap_iterations:.1f}")
    print(f"  Content success rate:     {metrics.content_success_rate:.1%}")
    print(f"  Avg failed nodes:         {metrics.avg_failed_nodes_per_gen:.1f}")
    print(f"  Avg generation time:      {metrics.avg_generation_time_sec:.1f}s")
    print(f"  Avg tokens:               {metrics.avg_total_tokens:,.0f}")
    print(f"  Avg cost:                 ${metrics.avg_cost_usd:.4f}")
    print(f"  Node type distribution:   {dict(metrics.node_type_distribution)}")


def _print_structural_summary(reports: list[StructuralReport]) -> None:
    n = len(reports)
    passed = sum(1 for r in reports if r.passed)
    print(f"\n{'='*50}")
    print(f"  Structural Checks")
    print(f"{'='*50}")
    print(f"  Pass rate:  {passed/n:.1%} ({passed}/{n})")

    # Aggregate failure types
    failure_counter: Counter[str] = Counter()
    total_nodes_checked = 0
    for r in reports:
        for f in r.failures:
            failure_counter[f"{f.check}: {f.detail}"] += 1
        total_nodes_checked += r.total_checks

    if failure_counter:
        print("  Common failures:")
        for desc, count in failure_counter.most_common(10):
            print(f"    - {desc}: {count}")


def _print_judge_summary(results: list[MultiJudgeResult]) -> None:
    if not results:
        return

    print(f"\n{'='*50}")
    print(f"  LLM Judge Scores (N={len(results)})")
    print(f"{'='*50}")

    # Collect model names
    model_names = [ms.model_name for ms in results[0].model_scores]
    short_names = [m.split("/")[-1] for m in model_names]

    # Header
    header = f"  {'':16s}" + "".join(f"{s:>12s}" for s in short_names) + f"{'Avg':>8s}{'Std':>8s}"
    print(header)
    print("  " + "-" * (len(header) - 2))

    # Per-dimension averages across all generations
    for dim in DIMENSIONS:
        per_model_avgs: list[float] = []
        for mi in range(len(model_names)):
            scores = [r.model_scores[mi].result.model_dump()[dim]["score"] for r in results]
            per_model_avgs.append(sum(scores) / len(scores))

        avg_all = sum(per_model_avgs) / len(per_model_avgs)
        std_all = statistics.stdev(per_model_avgs) if len(per_model_avgs) > 1 else 0.0

        row = f"  {dim:16s}"
        for avg in per_model_avgs:
            row += f"{avg:12.1f}"
        row += f"{avg_all:8.1f}{std_all:8.2f}"
        print(row)

    # Overall
    overall_avgs = [r.overall_mean for r in results]
    overall_mean = sum(overall_avgs) / len(overall_avgs)
    print(f"\n  Overall average: {overall_mean:.2f}")


def _save_results(result: EvalResult) -> Path:
    """Save evaluation results to data/eval/ as JSON."""
    out_dir = Path("data/eval")
    out_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    path = out_dir / f"eval_{ts}.json"
    path.write_text(
        json.dumps(result.model_dump(), ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    return path


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="CourseGen Evaluation Pipeline")
    parser.add_argument("--id", type=str, default=None, help="Evaluate a specific generation record ID")
    parser.add_argument("--no-llm-judge", action="store_true", help="Skip Layer 3 (LLM judge) to save cost")
    parser.add_argument("--list", action="store_true", help="List all generation records and exit")
    args = parser.parse_args()

    if args.list:
        summaries = list_generations(limit=200)
        if not summaries:
            print("No generation records found.")
            raise SystemExit(0)
        print(f"{'ID':<40s} {'Date':<22s} {'Nodes':>5s}  Topic")
        print("-" * 100)
        for s in summaries:
            date_str = s["created_at"].strftime("%Y-%m-%d %H:%M") if s.get("created_at") else "N/A"
            print(f"{s['id']:<40s} {date_str:<22s} {s.get('node_count', 0):>5d}  {s['topic']}")
        raise SystemExit(0)

    # Load data
    print("Loading generation records ...")
    generations = _load_all_generations(args.id)
    print(f"Loaded {len(generations)} record(s).")

    # Layer 1: Pipeline Metrics
    metrics = compute_pipeline_metrics(generations)
    _print_pipeline_metrics(metrics)

    # Layer 2: Structural Checks
    print("\nRunning structural checks ...")
    structural_reports: list[StructuralReport] = []
    for gen in generations:
        report = run_structural_checks(gen)
        structural_reports.append(report)
    _print_structural_summary(structural_reports)

    passed = sum(1 for r in structural_reports if r.passed)
    structural_pass_rate = passed / len(structural_reports) if structural_reports else 0.0

    # Layer 3: LLM Judge
    judge_results: list[MultiJudgeResult] | None = None
    if not args.no_llm_judge:
        print("\nRunning LLM judge evaluations ...")
        judge_results = []
        for i, gen in enumerate(generations, 1):
            print(f"\n[{i}/{len(generations)}] Topic: {gen['topic']}")
            result = judge_multi(gen)
            judge_results.append(result)
        _print_judge_summary(judge_results)
    else:
        print("\nSkipping LLM judge (--no-llm-judge).")

    # Save results
    eval_result = EvalResult(
        pipeline_metrics=metrics,
        structural_reports=structural_reports,
        structural_pass_rate=structural_pass_rate,
        judge_results=judge_results,
    )
    path = _save_results(eval_result)
    print(f"\nResults saved to: {path}")


if __name__ == "__main__":
    main()
