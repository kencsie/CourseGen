from coursegen.schemas import RoadmapValidationResult
from langchain.chat_models import init_chat_model
from coursegen.prompts.roadmap import ROADMAP_CRITIC_PROMPT
from coursegen.schemas import RoadmapState, ContextSchema
from langgraph.runtime import Runtime
import logging

logger = logging.getLogger(__name__)

def _get_external_knowledge(state: RoadmapState) -> str:
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


def roadmap_critic_node(state: RoadmapState, runtime: Runtime[ContextSchema]) -> dict:
    # 1. LLM 審核
    model = init_chat_model(
        model=runtime.context.roadmap_critic_model,
        model_provider="openai",
        api_key=runtime.context.openrouter_api_key,
        base_url=runtime.context.base_url,
        temperature=0,
    )
    model_structured = model.with_structured_output(RoadmapValidationResult).with_retry(
        stop_after_attempt=3,
    )
    result = model_structured.invoke(
        ROADMAP_CRITIC_PROMPT.format(
            question=state["question"],
            user_preferences=state["user_preferences"],
            roadmap=state["roadmap"],
            external_knowledge=_get_external_knowledge(state),
        )
    )

    # 2. 結構性驗證
    structural_issues = _validate_dependency_ids(state["roadmap"])
    if structural_issues:
        result.is_valid = False
        result.feedback += (
            "\n\n【結構性錯誤】以下 dependency ID 不存在於節點清單中，"
            "請確保 dependencies 欄位只引用本 roadmap 中實際存在的節點 ID：\n"
            + "\n".join(f"- {issue}" for issue in structural_issues)
        )
        result.retry_target = "generation"

    # 3. iteration_count 遞增 + termination_reason
    current_iteration = state.get("iteration_count", 0) + 1
    if result.is_valid:
        termination_reason = "validation_passed"
    elif current_iteration >= runtime.context.max_iterations:
        termination_reason = f"max_iterations_reached ({runtime.context.max_iterations})"
    else:
        termination_reason = None

    # 4. feedback 累積
    existing = state.get("roadmap_feedback", [])
    new_entry = {
        "feedback": result.feedback,
        "retry_target": result.retry_target,
        "is_valid": result.is_valid,
        "iteration": current_iteration,
    }

    logger.info(
        f"迭代 {current_iteration}/{runtime.context.max_iterations} | "
        f"{'通過' if result.is_valid else '未通過'} | "
        f"retry_target: {result.retry_target}"
    )

    return {
        "roadmap_is_valid": result.is_valid,
        "roadmap_latest_feedback": result.feedback,
        "roadmap_feedback": existing + [new_entry],
        "roadmap_retry_target": result.retry_target,
        "iteration_count": current_iteration,
        "termination_reason": termination_reason,
        "validation_metadata": {
            "iteration": current_iteration,
            "has_structural_issues": bool(structural_issues),
        },
    }
