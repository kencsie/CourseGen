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
你是課程品質評估專家。請嚴格評估以下 AI 生成的學習課程。

## 重要：評估原則
- **不要使用你自己的知識來判斷內容正確性。** 你的訓練資料可能不包含最新版本更新。當 sources 描述了你不認識的功能時，信任 sources。
- **只根據課程中附帶的參考來源 (sources) 來判斷事實是否有依據。**
- 如果某個 claim 在 sources 的 snippet 中找不到對應的支撐，應視為「無法驗證」並扣分。
- 如果 content 的敘述與 sources snippet 的內容矛盾，應視為「錯誤」。

## 校準指引
- **5 分代表完全無瑕疵，應極少出現。** 如果你打算給 5 分，請先重新逐節點檢查一次，確認真的找不到任何問題。
- **先找問題，再給分。** 你必須在 reason 中先列出所有發現的問題（用 ❌ 標記）和優點（用 ✅ 標記），然後根據問題的數量和嚴重程度決定分數。如果你無法列出任何具體的 ✅ 優點和 ❌ 問題，說明你的審查不夠仔細，請重新檢查。
- **泛泛的讚美不構成理由。**「完全一致」「無明顯遺漏」等空泛結論不可接受。你必須舉出具體的節點 ID、claim、和對應的 source snippet 來支撐你的評分。

## 課程主題
{topic}

## 學習者設定
- 語言: {language}

## 學習路徑 (Roadmap)
{roadmap_json}

## 教學內容（每個節點包含 sources 欄位，列出該節點引用的參考來源與摘要）
{content_map_json}

## 評估要求
針對以下 5 個維度，各給 1-5 分並說明理由。

**理由格式要求**：每個維度的 reason 必須包含：
1. 至少 2 個具體發現（✅ 或 ❌），引用節點 ID 和內容片段
2. 基於發現得出的評分判斷

### 評分標準
- accuracy (事實準確性，基於 sources 驗證):
  1=多處 claim 與 sources 矛盾或完全無 sources 支撐
  2=有明確矛盾，且多處 claim 無法在 sources 中驗證
  3=大致有 sources 支撐，但有 1-2 處 claim 找不到依據或措辭誇大
  4=絕大多數 claim 有 sources 支撐，僅有極少數細節無法驗證（如具體數字來自第三方）
  5=逐條查核後，所有事實性 claim 都能在 sources snippet 中找到直接對應依據
- completeness (完整性):
  1=大量遺漏關鍵知識
  2=僅涵蓋部分核心概念，多個重要面向缺失
  3=涵蓋主要概念但有明顯缺口（如重要子主題缺少獨立節點）
  4=涵蓋全面，僅有次要面向未深入
  5=全面涵蓋該主題核心，無明顯遺漏
- structure (結構合理性):
  1=學習順序混亂
  2=多處前置知識斷層或不必要的依賴
  3=大致合理但有部分跳躍或孤立支線
  4=循序漸進，僅有細微的依賴設計可改進
  5=完美的學習路徑，無前置知識斷層，所有支線都收斂
- practicality (實用性):
  1=純理論、無法應用
  2=有少量範例但過於抽象
  3=有具體範例但部分操作缺乏細節或無法驗證
  4=範例具體可用，學完大致能動手，僅少數場景缺乏指引
  5=所有範例都具體可操作，涵蓋常見場景，學完能直接應用
- citation (引用完整性):
  1=大量事實無引用
  2=部分核心 claim 有引用，但多處遺漏
  3=核心論點有引用但部分遺漏，或引用指向的 snippet 無法支撐 claim
  4=引用完整，僅極少數引用不夠精確
  5=所有事實性陳述都有準確引用，教學性敘述合理不引用\
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
