"""Layer 3: Multi-model LLM-as-Judge evaluation."""
from __future__ import annotations

import json
import os
import statistics

from langchain.chat_models import init_chat_model

from coursegen.eval.schemas import (
    DimensionAggregate,
    JudgeResult,
    ModelScore,
    MultiJudgeResult,
)

DEFAULT_JUDGES = [
    "anthropic/claude-sonnet-4.6",
    "openai/gpt-5.2",
    "google/gemini-3.1-pro-preview",
]

DIMENSIONS = ["accuracy", "completeness", "structure", "practicality", "citation"]

_JUDGE_PROMPT = """\
你是課程品質評估專家。請評估以下 AI 生成的學習課程。

## 重要：評估原則
- **不要使用你自己的知識來判斷內容正確性。** 你可能不熟悉這個主題的最新資訊。
- **只根據課程中附帶的參考來源 (sources) 來判斷事實是否有依據。**
- 如果某個 claim 在 sources 的 snippet 中找不到對應的支撐，應視為「無法驗證」並扣分。
- 如果 content 的敘述與 sources snippet 的內容矛盾，應視為「錯誤」。

## 課程主題
{topic}

## 學習者設定
- 語言: {language}

## 學習路徑 (Roadmap)
{roadmap_json}

## 教學內容（每個節點包含 sources 欄位，列出該節點引用的參考來源與摘要）
{content_map_json}

## 評估要求
針對以下 5 個維度，各給 1-5 分並說明理由。理由中必須引用具體的節點 ID 和內容片段作為證據。

### 評分標準
- accuracy (事實準確性，基於 sources 驗證): 1=多處 claim 與 sources 矛盾或完全無 sources 支撐 3=大致有 sources 支撐但部分 claim 找不到依據 5=所有事實性 claim 都能在 sources snippet 中找到對應依據
- completeness (完整性): 1=大量遺漏關鍵知識 3=涵蓋主要概念但有缺口 5=全面涵蓋該主題核心
- structure (結構合理性): 1=學習順序混亂 3=大致合理但部分跳躍 5=循序漸進、無前置知識斷層
- practicality (實用性): 1=純理論、無法應用 3=有範例但不夠具體 5=學完能直接動手
- citation (引用完整性): 1=大量事實無引用 3=核心論點有引用但部分遺漏 5=事實性陳述都有引用，教學性敘述合理不引用\
"""


def _get_judge_models() -> list[str]:
    """Read judge model names from env vars or use defaults."""
    models = []
    for i, default in enumerate(DEFAULT_JUDGES, start=1):
        models.append(os.environ.get(f"JUDGE_MODEL_{i}", default))
    return models


def _build_prompt(generation: dict) -> str:
    """Build the judge prompt from a generation record."""
    # Strip reasoning fields from content to reduce token usage
    content_map = generation.get("content_map") or {}
    clean_content: dict[str, dict] = {}
    for nid, content in content_map.items():
        clean_content[nid] = {k: v for k, v in content.items() if k != "reasoning"}

    return _JUDGE_PROMPT.format(
        topic=generation["topic"],
        language=generation.get("language", "N/A"),
        roadmap_json=json.dumps(generation.get("roadmap", {}), ensure_ascii=False, indent=2),
        content_map_json=json.dumps(clean_content, ensure_ascii=False, indent=2),
    )


def judge_single(generation: dict, model_name: str) -> JudgeResult:
    """Score one generation with one judge model.

    Uses OpenRouter via ``init_chat_model`` with ``model_provider="openai"``.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    base_url = os.environ.get("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

    model = init_chat_model(
        model=model_name,
        model_provider="openai",
        api_key=api_key,
        base_url=base_url,
        temperature=0,
    )
    structured = model.with_structured_output(JudgeResult).with_retry(stop_after_attempt=3)

    prompt = _build_prompt(generation)
    return structured.invoke(prompt)


def judge_multi(generation: dict) -> MultiJudgeResult:
    """Score one generation with all configured judge models and aggregate."""
    models = _get_judge_models()
    gen_id = generation["id"]
    topic = generation["topic"]

    model_scores: list[ModelScore] = []
    for model_name in models:
        print(f"  Judging with {model_name} ...")
        result = judge_single(generation, model_name)
        model_scores.append(ModelScore(model_name=model_name, result=result))

    # Aggregate per dimension
    aggregate: dict[str, DimensionAggregate] = {}
    all_means: list[float] = []
    for dim in DIMENSIONS:
        scores = [getattr(ms.result, dim).score for ms in model_scores]
        mean = statistics.mean(scores)
        std = statistics.stdev(scores) if len(scores) > 1 else 0.0
        aggregate[dim] = DimensionAggregate(mean=mean, std=std, scores=scores)
        all_means.append(mean)

    overall_mean = statistics.mean(all_means)
    overall_std = statistics.stdev(all_means) if len(all_means) > 1 else 0.0

    return MultiJudgeResult(
        generation_id=gen_id,
        topic=topic,
        model_scores=model_scores,
        aggregate=aggregate,
        overall_mean=overall_mean,
        overall_std=overall_std,
    )
