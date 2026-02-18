from coursegen.schemas import RoadmapValidationResult
from langchain.chat_models import init_chat_model
from coursegen.prompts.roadmap import ROADMAP_CRITIC_PROMPT
from coursegen.schemas import State, ContextSchema
from langgraph.runtime import Runtime
import logging

logger = logging.getLogger(__name__)

def _get_external_knowledge(state: State) -> str:
    """Helper function to extract external knowledge from state"""
    knowledge_context = state.get("knowledge_context") or {}
    return knowledge_context.get("synthesized_knowledge", "")


def _validate_dependency_ids(roadmap: dict) -> list[str]:
    """確認 roadmap 中所有節點的 dependency ID 都存在於節點清單。"""
    nodes = roadmap.get("nodes", [])
    all_ids = {node["id"] for node in nodes}
    issues = []
    for node in nodes:
        for dep_id in node.get("dependencies", []):
            if dep_id not in all_ids:
                issues.append(
                    f"節點 '{node['id']}' 的 dependency '{dep_id}' 不存在於節點清單"
                )
    return issues


def critic_1_node(state: State, runtime: Runtime[ContextSchema]) -> dict:
    logger.info(f"Critic 1 審核中（{runtime.context.critic_1_model}）")
    model = init_chat_model(
        model=runtime.context.critic_1_model,
        model_provider="openai",  # OpenRouter 使用 OpenAI-compatible API
        api_key=runtime.context.openrouter_api_key,
        base_url=runtime.context.base_url,
        temperature=0
    )
    model_structured = model.with_structured_output(RoadmapValidationResult)
    response = model_structured.invoke(
        ROADMAP_CRITIC_PROMPT.format(
            question=state["question"],
            user_preferences=state["user_preferences"],
            roadmap=state["roadmap"],
            external_knowledge=_get_external_knowledge(state),
        )
    )
    response.critic_name = "critic_1"
    response.model_name = runtime.context.critic_1_model
    logger.info(
        f"Critic 1 結果: {'通過' if response.is_valid else '未通過'} | "
        f"回饋: {response.feedback[:80]}..."
    )
    return {
        "critics": [response.model_dump()]
    }


def critic_2_node(state: State, runtime: Runtime[ContextSchema]) -> dict:
    logger.info(f"Critic 2 審核中（{runtime.context.critic_2_model}）")
    model = init_chat_model(
        model=runtime.context.critic_2_model,
        model_provider="openai",  # OpenRouter 使用 OpenAI-compatible API
        api_key=runtime.context.openrouter_api_key,
        base_url=runtime.context.base_url,
        temperature=0
    )
    model_structured = model.with_structured_output(RoadmapValidationResult)
    response = model_structured.invoke(
        ROADMAP_CRITIC_PROMPT.format(
            question=state["question"],
            user_preferences=state["user_preferences"],
            roadmap=state["roadmap"],
            external_knowledge=_get_external_knowledge(state),
        )
    )
    response.critic_name = "critic_2"
    response.model_name = runtime.context.critic_2_model
    logger.info(
        f"Critic 2 結果: {'通過' if response.is_valid else '未通過'} | "
        f"回饋: {response.feedback[:80]}..."
    )
    return {
        "critics": [response.model_dump()]
    }


def critic_3_node(state: State, runtime: Runtime[ContextSchema]) -> dict:
    logger.info(f"Critic 3 審核中（{runtime.context.critic_3_model}）")
    model = init_chat_model(
        model=runtime.context.critic_3_model,
        model_provider="openai",  # OpenRouter 使用 OpenAI-compatible API
        api_key=runtime.context.openrouter_api_key,
        base_url=runtime.context.base_url,
        temperature=0
    )
    model_structured = model.with_structured_output(RoadmapValidationResult)
    response = model_structured.invoke(
        ROADMAP_CRITIC_PROMPT.format(
            question=state["question"],
            user_preferences=state["user_preferences"],
            roadmap=state["roadmap"],
            external_knowledge=_get_external_knowledge(state),
        )
    )
    response.critic_name = "critic_3"
    response.model_name = runtime.context.critic_3_model
    logger.info(
        f"Critic 3 結果: {'通過' if response.is_valid else '未通過'} | "
        f"回饋: {response.feedback[:80]}..."
    )
    return {
        "critics": [response.model_dump()]
    }


def aggregator_node(state: State, runtime: Runtime[ContextSchema]) -> dict:
    """
    根據多數決，得出此roadmap是否正確
    """

    critics = [RoadmapValidationResult(**c) for c in state["critics"]]
    valid_votes = sum(1 for c in critics if c.is_valid)
    is_valid = valid_votes >= 2  # 至少要2/3，才算通過
    feedback = [c.model_dump() for c in critics]

    # 結構性驗證
    structural_issues = _validate_dependency_ids(state["roadmap"])
    if structural_issues:
        logger.warning(f"Roadmap dependency ID 驗證失敗: {structural_issues}")
        feedback.append({
            "critic_name": "structural_validator",
            "model_name": "deterministic",
            "feedback": (
                "【結構性錯誤】以下 dependency ID 不存在於節點清單中，"
                "請確保 dependencies 欄位只引用本 roadmap 中實際存在的節點 ID：\n"
                + "\n".join(f"- {issue}" for issue in structural_issues)
            ),
            "is_valid": False,
        })
        is_valid = False

    current_iteration = state.get("iteration_count", 0) + 1

    if is_valid:
        termination_reason = "validation_passed"
    elif current_iteration >= runtime.context.max_iterations:
        termination_reason = f"max_iterations_reached ({runtime.context.max_iterations})"
    else:
        termination_reason = None

    metadata = {
        "valid_votes": valid_votes,
        "total_critics": 3,
        "consensus_level": "unanimous" if valid_votes in [0, 3] else "majority",
        "iteration": current_iteration
    }

    logger.info(
        f"迭代次數：{current_iteration}/{runtime.context.max_iterations} | "
        f"同意數：{metadata['valid_votes']}/{metadata['total_critics']} | "
        f"共識：{metadata['consensus_level']} | "
        f"結果：{'通過' if is_valid else '未通過，觸發 retry'}"
    )

    return {
        "roadmap_is_valid": is_valid,
        "roadmap_feedback": feedback,
        "validation_metadata": metadata,
        "iteration_count": current_iteration,
        "termination_reason": termination_reason
    }

def roadmap_critic_node(state: State, runtime: Runtime[ContextSchema]):
    model = init_chat_model(
        model=runtime.context.model_name,
        model_provider="openai",  # OpenRouter 使用 OpenAI-compatible API
        api_key=runtime.context.openrouter_api_key,
        base_url=runtime.context.base_url,
    )
    model_structured = model.with_structured_output(RoadmapValidationResult)
    response = model_structured.invoke(
        ROADMAP_CRITIC_PROMPT.format(
            question=state["question"],
            user_preferences=state["user_preferences"],
            roadmap=state["roadmap"],
            external_knowledge=_get_external_knowledge(state),
        )
    )
    return {
        "roadmap_feedback": response.feedback,
        "roadmap_is_valid": response.is_valid,
    }
