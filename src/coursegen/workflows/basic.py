from coursegen.schemas import Language, UserPreferences, LearningGoal, DifficultyLevel
import os
from coursegen.agents.roadmap import roadmap_node, roadmap_critic_node
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


def conditional_edge(state: State) -> bool:
    return state["roadmap_is_valid"]


builder = StateGraph(State, context_schema=ContextSchema)
builder.add_node("roadmap_node", roadmap_node)
builder.add_node("roadmap_critic_node", roadmap_critic_node)
builder.add_edge(START, "roadmap_node")
builder.add_edge("roadmap_node", "roadmap_critic_node")
builder.add_conditional_edges(
    "roadmap_critic_node", conditional_edge, {True: "__end__", False: "roadmap_node"}
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
            "question": "How to pass celeste 7C?",
            "user_preferences": prefs_novice.to_prompt_context(),
        },
        context={
            "model_name": "google/gemini-3-flash-preview",
            "base_url": os.getenv("BASE_URL"),
            "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
        },
        config={"callbacks": [langfuse_handler]},
    )

    to_mermaid(result["roadmap"])
    # print(result)
