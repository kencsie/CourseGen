from coursegen.schemas import Language, UserPreferences
import os
from coursegen.agents.roadmap import roadmap_node
from coursegen.agents.knowledge_search import knowledge_search_node
from coursegen.agents.critic import roadmap_critic_node
from coursegen.agents.content import (
    content_planning_node,
    content_knowledge_search_node,
    content_generation_node,
    content_critic_node,
    content_router,
    content_advance_node,
    content_should_continue,
)
from coursegen.schemas import AppState, RoadmapState, ContentState, ContextSchema
from langgraph.graph import StateGraph, START
from langgraph.runtime import Runtime


def to_mermaid(roadmap_data):
    print("graph TD")
    for node in roadmap_data["nodes"]:
        # 處理 label 中的括號，避免 Mermaid 語法錯誤
        safe_label = node["label"].replace("(", "").replace(")", "")
        print(f'    {node["id"]}["{safe_label}"]')

        for parent in node["dependencies"]:
            print(f"    {parent} --> {node['id']}")


def roadmap_router(state: RoadmapState, runtime: Runtime[ContextSchema]) -> str:
    """Roadmap 驗證後的路由：通過/達上限則結束，否則根據 retry_target 回到 search 或 generation。"""
    if (
        state.get("roadmap_is_valid", False)
        or state.get("iteration_count", 0) >= runtime.context.max_iterations
    ):
        return "__end__"
    if state.get("roadmap_retry_target") == "search":
        return "search"
    return "generation"


# === RoadmapSubgraph（RoadmapState）===
roadmap_builder = StateGraph(RoadmapState, context_schema=ContextSchema)

roadmap_builder.add_node("knowledge_search_node", knowledge_search_node)
roadmap_builder.add_node("roadmap_node", roadmap_node)
roadmap_builder.add_node("roadmap_critic_node", roadmap_critic_node)

roadmap_builder.add_edge(START, "knowledge_search_node")
roadmap_builder.add_edge("knowledge_search_node", "roadmap_node")
roadmap_builder.add_edge("roadmap_node", "roadmap_critic_node")
roadmap_builder.add_conditional_edges(
    "roadmap_critic_node",
    roadmap_router,
    {"__end__": "__end__", "search": "knowledge_search_node", "generation": "roadmap_node"},
)

roadmap_subgraph = roadmap_builder.compile()

# === Inner subgraph: 單次 content node 的完整處理 ===
content_iteration_builder = StateGraph(ContentState, context_schema=ContextSchema)

content_iteration_builder.add_node("content_knowledge_search_node", content_knowledge_search_node)
content_iteration_builder.add_node("content_generation_node", content_generation_node)
content_iteration_builder.add_node("content_critic_node", content_critic_node)
content_iteration_builder.add_node("content_advance_node", content_advance_node)

content_iteration_builder.add_edge(START, "content_knowledge_search_node")
content_iteration_builder.add_edge("content_knowledge_search_node", "content_generation_node")
content_iteration_builder.add_edge("content_generation_node", "content_critic_node")
content_iteration_builder.add_conditional_edges(
    "content_critic_node",
    content_router,
    {
        "advance": "content_advance_node",
        "advance_with_failure": "content_advance_node",
        "search": "content_knowledge_search_node",
        "generation": "content_generation_node",
    },
)
content_iteration_builder.add_edge("content_advance_node", "__end__")

content_iteration_subgraph = content_iteration_builder.compile()

# === Outer ContentSubgraph: planning + loop ===
content_builder = StateGraph(ContentState, context_schema=ContextSchema)

content_builder.add_node("content_planning_node", content_planning_node)
content_builder.add_node("content_iteration", content_iteration_subgraph)

content_builder.add_edge(START, "content_planning_node")
content_builder.add_edge("content_planning_node", "content_iteration")
content_builder.add_conditional_edges(
    "content_iteration",
    content_should_continue,
    {
        "continue": "content_iteration",
        "__end__": "__end__",
    },
)

content_subgraph = content_builder.compile()

# === Main Graph（AppState）===
builder = StateGraph(AppState, context_schema=ContextSchema)
builder.add_node("roadmap", roadmap_subgraph)
builder.add_node("content", content_subgraph)
builder.add_edge(START, "roadmap")
builder.add_edge("roadmap", "content")

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

    prefs_novice = UserPreferences(language=Language.ZH_TW)

    result = graph.invoke(
        {
            "question": "How to learn Java Edition 1.21.11?",
            "user_preferences": prefs_novice.to_prompt_context(),
        },
        context={
            "model_name": "google/gemini-3-flash-preview",
            "base_url": os.getenv("BASE_URL"),
            "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
            "roadmap_critic_model": "google/gemini-3-flash-preview",
            "max_iterations": 3,
            "tavily_api_key": os.getenv("TAVILY_KEY"),
            "content_model": "google/gemini-3-flash-preview",
            "content_max_retries": 3,
        },
        config={"callbacks": [langfuse_handler]},
    )

    to_mermaid(result["roadmap"])

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
