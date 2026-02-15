from coursegen.schemas import Language, UserPreferences, LearningGoal, DifficultyLevel
import os
from coursegen.agents.roadmap import roadmap_node
from coursegen.agents.knowledge_search import knowledge_search_node
from coursegen.agents.critic import (
    critic_1_node,
    critic_2_node,
    critic_3_node,
    aggregator_node,
)
from coursegen.agents.content import (
    content_planning_node,
    content_knowledge_search_node,
    content_generation_node,
    content_critic_node,
    content_router,
    content_advance_node,
    content_should_continue,
)
from coursegen.schemas import State
from langgraph.graph import StateGraph, START
from coursegen.schemas import ContextSchema
from langgraph.runtime import Runtime


def to_mermaid(roadmap_data):
    print("graph TD")
    for node in roadmap_data["nodes"]:
        # 處理 label 中的括號，避免 Mermaid 語法錯誤
        safe_label = node["label"].replace("(", "").replace(")", "")
        print(f'    {node["id"]}["{safe_label}"]')

        for parent in node["dependencies"]:
            print(f"    {parent} --> {node['id']}")


def conditional_edge(state: State, runtime: Runtime[ContextSchema]) -> str:
    """Roadmap 驗證後的路由：通過則進入 content generation，否則重新生成。"""
    if (
        state.get("roadmap_is_valid", False)
        or state.get("iteration_count", 0) >= runtime.context.max_iterations
    ):
        return "content_planning_node"
    return "roadmap_node"


builder = StateGraph(State, context_schema=ContextSchema)

# === Roadmap 階段 ===
builder.add_node("knowledge_search_node", knowledge_search_node)
builder.add_node("roadmap_node", roadmap_node)
builder.add_node("critic_1_node", critic_1_node)
builder.add_node("critic_2_node", critic_2_node)
builder.add_node("critic_3_node", critic_3_node)
builder.add_node("aggregator_node", aggregator_node)

builder.add_edge(START, "knowledge_search_node")
builder.add_edge("knowledge_search_node", "roadmap_node")
builder.add_edge("roadmap_node", "critic_1_node")
builder.add_edge("roadmap_node", "critic_2_node")
builder.add_edge("roadmap_node", "critic_3_node")
builder.add_edge("critic_1_node", "aggregator_node")
builder.add_edge("critic_2_node", "aggregator_node")
builder.add_edge("critic_3_node", "aggregator_node")
builder.add_conditional_edges(
    "aggregator_node",
    conditional_edge,
    {"content_planning_node": "content_planning_node", "roadmap_node": "roadmap_node"},
)

# === Content Generation Loop ===
builder.add_node("content_planning_node", content_planning_node)
builder.add_node("content_knowledge_search_node", content_knowledge_search_node)
builder.add_node("content_generation_node", content_generation_node)
builder.add_node("content_critic_node", content_critic_node)
builder.add_node("content_advance_node", content_advance_node)

builder.add_edge("content_planning_node", "content_knowledge_search_node")
builder.add_edge("content_knowledge_search_node", "content_generation_node")
builder.add_edge("content_generation_node", "content_critic_node")
builder.add_conditional_edges(
    "content_critic_node",
    content_router,
    {
        "advance": "content_advance_node",
        "advance_with_failure": "content_advance_node",
        "retry": "content_generation_node",
    },
)
builder.add_conditional_edges(
    "content_advance_node",
    content_should_continue,
    {
        "continue": "content_knowledge_search_node",
        "__end__": "__end__",
    },
)

graph = builder.compile()

if __name__ == "__main__":
    from langfuse.langchain import CallbackHandler
    from dotenv import load_dotenv
    import logging
    import json

    logging.basicConfig(
        level=logging.INFO,
        format="{asctime} | {name:<20} | {levelname:<8} | {message}",
        datefmt="%Y-%m-%d %H:%M:%S",
        style="{",
    )

    load_dotenv()

    langfuse_handler = CallbackHandler()

    prefs_novice = UserPreferences(
        level=DifficultyLevel.BEGINNER,
        goal=LearningGoal.QUICK_START,
        language=Language.ZH_TW,
    )

    result = graph.invoke(
        {
            "question": "How to learn Java Edition 1.21.11?",
            "user_preferences": prefs_novice.to_prompt_context(),
            "iteration_count": 0,
        },
        context={
            "model_name": "google/gemini-3-flash-preview",
            "base_url": os.getenv("BASE_URL"),
            "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
            "critic_1_model": "anthropic/claude-4.5-sonnet",
            "critic_2_model": "openai/gpt-4o",
            "critic_3_model": "google/gemini-3-flash-preview",
            "max_iterations": 3,
            "tavily_api_key": os.getenv("TAVILY_KEY"),
            "content_model": "google/gemini-3-flash-preview",
            "content_max_retries": 2,
        },
        config={"callbacks": [langfuse_handler]},
    )

    to_mermaid(result["roadmap"])

    print(f"\n終止原因: {result.get('termination_reason', 'unknown')}")
    print(f"總迭代次數: {result.get('iteration_count', 0)}")

    # Content generation 結果
    content_map = result.get("content_map", {})
    failed_nodes = result.get("content_failed_nodes", [])
    content_order = result.get("content_order", [])
    roadmap_nodes = {n["id"]: n for n in result["roadmap"]["nodes"]}

    print(f"\n{'='*60}")
    print(f"課程主題: {result['roadmap']['topic']}")
    print(f"成功生成: {len(content_map)} / {len(content_order)} 個節點")
    print(f"失敗節點: {failed_nodes if failed_nodes else '無'}")
    print(f"{'='*60}")

    # 按拓撲順序輸出每個節點的 roadmap 資訊 + 生成的內容
    for node_id in content_order:
        node = roadmap_nodes.get(node_id, {})
        is_failed = node_id in failed_nodes
        status = "FAILED" if is_failed else "OK"

        print(f"\n{'='*60}")
        print(f"[{status}] {node_id} ({node.get('type', '?')})")
        print(f"名稱: {node.get('label', '?')}")
        print(f"描述: {node.get('description', '?')}")
        print(f"依賴: {node.get('dependencies', [])}")
        print(f"{'─'*60}")

        content = content_map.get(node_id)
        if content:
            print(json.dumps(content, ensure_ascii=False, indent=2))
        else:
            print("（未生成內容）")
