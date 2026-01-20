import os
from tavily import TavilyClient
from coursegen.schemas import State


def search_node(state: State):
    client = TavilyClient(os.getenv("TAVILY_KEY"))
    response = client.search(
        query=str(state["messages"][-1].content),
        search_depth="advanced",
        include_usage=True,
        # include_raw_content="markdown"
    )
    return {"retrieved_doc": response["results"]}
