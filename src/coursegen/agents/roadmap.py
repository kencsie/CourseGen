from coursegen.schemas import RoadmapValidationResult, Roadmap
from langchain.chat_models import init_chat_model
from coursegen.prompts.roadmap import ROADMAP_GENERATION_PROMPT, ROADMAP_CRITIC_PROMPT
from coursegen.schemas import State, ContextSchema
from langgraph.runtime import Runtime


def roadmap_node(state: State, runtime: Runtime[ContextSchema]):
    model = init_chat_model(
        model=runtime.context.model_name,
        model_provider="openai",  # OpenRouter 使用 OpenAI-compatible API
        api_key=runtime.context.openrouter_api_key,
        base_url=runtime.context.base_url,
        temperature=0.1,  # 使用保守的溫度，建立roadmap
    )
    model_structured = model.with_structured_output(Roadmap)
    # 取得知識內容
    knowledge_context = state.get("knowledge_context") or {}

    roadmap = model_structured.invoke(
        ROADMAP_GENERATION_PROMPT.format(
            question=state["question"],
            user_preferences=state["user_preferences"],
            roadmap_feedback=state.get(  # 第一次會不存在，所以用get
                "roadmap_feedback", ""
            ),
            roadmap=state.get(  # 第一次會不存在，所以用get
                "roadmap", ""
            ),
            external_knowledge=knowledge_context.get(  # 有可能不存在，所以用get
                "synthesized_knowledge", ""
            ),
        )
    )

    return {
        "roadmap": roadmap.model_dump(),
        "critics": [],  # 清空上一輪的 critics 結果
    }
