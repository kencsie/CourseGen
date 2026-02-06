from coursegen.schemas import RoadmapValidationResult, AggregatedFeedback, StructuredIssue
from langchain.chat_models import init_chat_model
from coursegen.prompts.roadmap import ROADMAP_CRITIC_PROMPT_V2
from coursegen.schemas import State, ContextSchema
from langgraph.runtime import Runtime
from collections import defaultdict
from typing import List


def synthesize_feedback(critics: List[RoadmapValidationResult]) -> AggregatedFeedback:
    """
    從多個 critics 中提取共識：
    - 找出 2+ critics 都提到的問題（consensus_issues）
    - 收集所有 critical severity 的問題
    - 生成優先修正的總結
    """
    # 收集所有 critical issues
    critical_issues = []
    for critic in critics:
        for issue in critic.issues:
            if issue.severity == "critical":
                critical_issues.append(issue)

    # 按問題類型和位置分組，找出共識問題
    issue_groups = defaultdict(list)
    for critic in critics:
        for issue in critic.issues:
            key = (issue.issue_type, issue.location)
            issue_groups[key].append(issue)

    # 2+ critics 同意的問題
    consensus_issues = []
    for key, issues in issue_groups.items():
        if len(issues) >= 2:
            # 使用第一個 issue 作為代表
            consensus_issues.append(issues[0])

    # 生成總結
    is_valid = sum(1 for c in critics if c.is_valid) >= 2
    summary_parts = []

    if critical_issues:
        summary_parts.append(f"發現 {len(critical_issues)} 個嚴重問題需要立即修正。")

    if consensus_issues:
        summary_parts.append(f"有 {len(consensus_issues)} 個問題被多位評審共同指出。")

    if not is_valid:
        summary_parts.append("請優先修正嚴重問題和共識問題，然後重新生成 roadmap。")
    else:
        summary_parts.append("整體結構良好，已通過驗證。")

    summary = " ".join(summary_parts) if summary_parts else "未發現重大問題。"

    return AggregatedFeedback(
        is_valid=is_valid,
        critical_issues=critical_issues,
        consensus_issues=consensus_issues,
        summary=summary
    )


def critic_1_node(state: State, runtime: Runtime[ContextSchema]) -> dict:
    model = init_chat_model(
        model=runtime.context.critic_1_model,
        model_provider="openai",  # OpenRouter 使用 OpenAI-compatible API
        api_key=runtime.context.openrouter_api_key,
        base_url=runtime.context.base_url,
        temperature=0
    )
    model_structured = model.with_structured_output(RoadmapValidationResult)
    response = model_structured.invoke(
        ROADMAP_CRITIC_PROMPT_V2.format(
            question=state["question"],
            user_preferences=state["user_preferences"],
            roadmap=state["roadmap"],
        )
    )
    response.critic_name = "critic_1"
    response.model_name = runtime.context.critic_1_model

    return {
        "critics": [response.model_dump()]
    }

def critic_2_node(state: State, runtime: Runtime[ContextSchema]) -> dict:
    model = init_chat_model(
        model=runtime.context.critic_2_model,
        model_provider="openai",  # OpenRouter 使用 OpenAI-compatible API
        api_key=runtime.context.openrouter_api_key,
        base_url=runtime.context.base_url,
        temperature=0
    )
    model_structured = model.with_structured_output(RoadmapValidationResult)
    response = model_structured.invoke(
        ROADMAP_CRITIC_PROMPT_V2.format(
            question=state["question"],
            user_preferences=state["user_preferences"],
            roadmap=state["roadmap"],
        )
    )
    response.critic_name = "critic_2"
    response.model_name = runtime.context.critic_2_model

    return {
        "critics": [response.model_dump()]
    }

def critic_3_node(state: State, runtime: Runtime[ContextSchema]) -> dict:
    model = init_chat_model(
        model=runtime.context.critic_3_model,
        model_provider="openai",  # OpenRouter 使用 OpenAI-compatible API
        api_key=runtime.context.openrouter_api_key,
        base_url=runtime.context.base_url,
        temperature=0
    )
    model_structured = model.with_structured_output(RoadmapValidationResult)
    response = model_structured.invoke(
        ROADMAP_CRITIC_PROMPT_V2.format(
            question=state["question"],
            user_preferences=state["user_preferences"],
            roadmap=state["roadmap"],
        )
    )
    response.critic_name = "critic_3"
    response.model_name = runtime.context.critic_3_model

    return {
        "critics": [response.model_dump()]
    }

def aggregator_node(state: State) -> dict:
    """根據多數決，得出此roadmap是否正確，並整合結構化回饋"""

    critics = [RoadmapValidationResult(**c) for c in state["critics"]]
    valid_votes = sum(1 for c in critics if c.is_valid)
    is_valid = valid_votes >= 2  # 至少要2/3，才算通過

    current_iteration = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 3)

    # 整合結構化回饋
    aggregated_feedback = synthesize_feedback(critics)

    # 設定終止原因
    termination_reason = None
    if is_valid:
        termination_reason = "validation_passed"
    elif current_iteration >= max_iterations:
        termination_reason = "max_iterations_reached"

    metadata = {
        "valid_votes": valid_votes,
        "total_critics": 3,
        "consensus_level": "unanimous" if valid_votes in [0, 3] else "majority",
        "iteration_count": current_iteration,
        "max_iterations": max_iterations,
        "critical_issue_count": len(aggregated_feedback.critical_issues),
        "consensus_issue_count": len(aggregated_feedback.consensus_issues)
    }

    # 保存原始 critics 和整合後的結構化回饋
    feedback = [c.model_dump() for c in critics]
    feedback.append({
        "aggregated": True,
        **aggregated_feedback.model_dump()
    })

    return {
        "roadmap_is_valid": is_valid,
        "roadmap_feedback": feedback,
        "validation_metadata": metadata,
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
        )
    )
    return {
        "roadmap_feedback": response.feedback,
        "roadmap_is_valid": response.is_valid,
    }
