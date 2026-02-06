from coursegen.schemas import RoadmapValidationResult, Roadmap
from langchain.chat_models import init_chat_model
from coursegen.prompts.roadmap import (
    ROADMAP_GENERATION_PROMPT_V3,
    ROADMAP_CRITIC_PROMPT,
    format_feedback_section,
    format_knowledge_context
)
from coursegen.schemas import State, ContextSchema
from langgraph.runtime import Runtime


def roadmap_node(state: State, runtime: Runtime[ContextSchema]):
    current_iteration = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 3)

    # 格式化外部知識上下文（如果存在）
    knowledge_section = ""
    knowledge_context = state.get("knowledge_context")
    if knowledge_context:
        knowledge_section = format_knowledge_context(knowledge_context)

    # 格式化結構化回饋（如果存在）
    feedback_section = ""
    roadmap_feedback = state.get("roadmap_feedback", [])
    if roadmap_feedback and current_iteration > 0:
        # 找到整合後的回饋（最後一個帶有 "aggregated": True 的項目）
        aggregated = None
        for item in reversed(roadmap_feedback):
            if isinstance(item, dict) and item.get("aggregated"):
                aggregated = item
                break

        if aggregated:
            feedback_section = format_feedback_section(aggregated, current_iteration)

    # 在 prompt 中加入迭代上下文提示（當不是第一次迭代時）
    iteration_context = ""
    if current_iteration > 0:
        iteration_context = f"\n\n⚠️ 這是第 {current_iteration + 1}/{max_iterations} 次迭代修正。請特別注意上述 Roadmap Feedback 中的問題並修正。"

    model = init_chat_model(
        model=runtime.context.model_name,
        model_provider="openai",  # OpenRouter 使用 OpenAI-compatible API
        api_key=runtime.context.openrouter_api_key,
        base_url=runtime.context.base_url,
        temperature=0.1,  # 使用保守的溫度，建立roadmap
    )
    model_structured = model.with_structured_output(Roadmap)

    # 組合完整的 prompt (使用 V3 prompt)
    base_prompt = ROADMAP_GENERATION_PROMPT_V3.format(
        knowledge_context=knowledge_section,  # 外部知識參考
        question=state["question"],
        user_preferences=state["user_preferences"],
        roadmap_feedback=feedback_section,  # 使用格式化的結構化回饋
        roadmap=state.get("roadmap", ""),
    )

    roadmap = model_structured.invoke(base_prompt + iteration_context)

    return {
        "roadmap": roadmap.model_dump(),
        "critics": [],  # 清空上一輪的 critics 結果
        "iteration_count": current_iteration + 1
    }