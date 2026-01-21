import os
from coursegen.agents.roadmap import roadmap_node
from coursegen.utils.tavily_search import search_node
from coursegen.schemas import State
from langgraph.graph import StateGraph, START, END
from coursegen.schemas import ContextSchema

builder = StateGraph(State, context_schema=ContextSchema)
builder.add_node("search_node", search_node)
builder.add_node("roadmap_node", roadmap_node)
builder.add_edge(START, "search_node")
builder.add_edge("search_node", "roadmap_node")
builder.add_edge("roadmap_node", END)
graph = builder.compile()

if __name__ == "__main__":
    from langfuse.langchain import CallbackHandler
    from langchain.messages import HumanMessage
    from dotenv import load_dotenv

    load_dotenv()

    langfuse_handler = CallbackHandler()

    result = graph.invoke(
        {"messages": [HumanMessage("How to pass celeste chapter 9?")]},
        context={
            "model_name": "gpt-4o",
            "base_url": os.getenv("BASE_URL"),
            "openrouter_api_key": os.getenv("OPENROUTER_API_KEY"),
        },
        config={"callbacks": [langfuse_handler]},
    )
    print(result)
