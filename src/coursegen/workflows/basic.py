from coursegen.schemas import Language, UserPreferences, LearningGoal, DifficultyLevel
import os
from coursegen.agents.roadmap import roadmap_node
from coursegen.agents.critic import critic_1_node, critic_2_node, critic_3_node, aggregator_node
from coursegen.utils.tavily_search import knowledge_search_node
from coursegen.schemas import State
from langgraph.graph import StateGraph, START
from coursegen.schemas import ContextSchema


def to_mermaid(roadmap_data):
    print("graph TD")
    for node in roadmap_data["nodes"]:
        # 處理 label 中的括號，避免 Mermaid 語法錯誤
        safe_label = node["label"].replace("(", "").replace(")", "")
        print(f'    {node["id"]}["{safe_label}"]')

        for parent in node["dependencies"]:
            print(f"    {parent} --> {node['id']}")


def conditional_edge(state: State) -> str:
    iteration_count = state.get("iteration_count", 0)
    max_iterations = state.get("max_iterations", 3)
    is_valid = state["roadmap_is_valid"]

    if iteration_count >= max_iterations:
        if not is_valid:
            print(f"⚠️  達到最大迭代次數 ({max_iterations})，接受當前 roadmap")
        return "__end__"

    return "__end__" if is_valid else "roadmap_node"


builder = StateGraph(State, context_schema=ContextSchema)
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
    "aggregator_node", conditional_edge
)
graph = builder.compile()

if __name__ == "__main__":
    from langfuse.langchain import CallbackHandler
    from dotenv import load_dotenv

    load_dotenv()

    langfuse_handler = CallbackHandler()

    prefs_novice = UserPreferences(
        level=DifficultyLevel.BEGINNER,
        goal=LearningGoal.QUICK_START,
        language=Language.ZH_TW,
    )

    result = graph.invoke(
        {
            "question": "How to learn present perfect continuous tense?",
            "user_preferences": prefs_novice.to_prompt_context(),
            "iteration_count": 0,
            "max_iterations": 3,
            "search_performed": False,
        },
        context={
            #"model_name": "google/gemini-3-flash-preview",
            "model_name": "microsoft/phi-4",
            "base_url": os.getenv("BASE_URL"),
            "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
            "critic_1_model": "anthropic/claude-4.5-sonnet",
            "critic_2_model": "openai/gpt-4o",
            "critic_3_model": "google/gemini-3-flash-preview",
        },
        config={"callbacks": [langfuse_handler]},
    )

    to_mermaid(result["roadmap"])
    print(f"\n✅ 終止原因: {result.get('termination_reason', 'N/A')}")
    print(f"📊 迭代次數: {result.get('iteration_count', 0)}/{result.get('max_iterations', 3)}")
    print(f"🎯 驗證狀態: {'通過' if result.get('roadmap_is_valid') else '未通過'}")
    print(f"🔍 知識搜尋: {'已執行' if result.get('search_performed') else '未執行'}")

    # 顯示知識上下文（如果有）
    if result.get("knowledge_context"):
        kc = result["knowledge_context"]
        print(f"\n📚 外部知識來源: {len(kc.get('results', []))} 個資源")
        print(f"   搜尋查詢: {kc.get('query', 'N/A')}")
    # print(result)
