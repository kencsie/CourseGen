from coursegen.schemas import State, ContextSchema, KnowledgeContext, SearchResult
from coursegen.prompts.knowledge_synthesis import KNOWLEDGE_SYNTHESIS_PROMPT
from langgraph.runtime import Runtime
from langchain.chat_models import init_chat_model
from tavily import TavilyClient
import logging

logger = logging.getLogger(__name__)


def knowledge_search_node(state: State, runtime: Runtime[ContextSchema]) -> dict:
    """
    在生成 roadmap 前，先搜尋外部知識
    """

    if not runtime.context.tavily_api_key:
        logger.warning("TAVILY API KEY 不存在，跳過此流程")
        return {}

    # 設定Tavily客戶端
    tavily_client = TavilyClient(api_key=runtime.context.tavily_api_key)

    logger.debug("Tavily搜尋中...")

    # 搜尋query
    response = tavily_client.search(
        query=state.get("question"),
        search_depth="advanced",
        include_raw_content="markdown",
    )

    # 整理成SearchResult物件串列
    search_results = []
    for result in response["results"]:
        search_results.append(
            SearchResult(
                title=result["title"],
                url=result["url"],
                content=result["content"],
                score=result["score"],
                raw_content=result["raw_content"],
            )
        )

    # 格式化內容為可讀形式
    formatted_results = "\n\n".join(
        [
            f"=== 來源 {i + 1}: {r.title} ===\n=== 關聯度分數:{r.score} ===\n{r.raw_content or r.content}"
            for i, r in enumerate(search_results)
        ]
    )

    # 呼叫LLM，統整檢索到內容
    model = init_chat_model(
        model=runtime.context.model_name,
        model_provider="openai",  # OpenRouter 使用 OpenAI-compatible API
        api_key=runtime.context.openrouter_api_key,
        base_url=runtime.context.base_url,
        temperature=0.1,
    )

    logger.debug("LLM統整中...")

    response = model.invoke(
        KNOWLEDGE_SYNTHESIS_PROMPT.format(
            question=state.get("question"), search_results=formatted_results
        )
    )

    # 回傳 KnowledgeContext
    return {
        "knowledge_context": KnowledgeContext(
            query=state.get("question"),
            results=search_results,
            synthesized_knowledge=str(response.content),
        ).model_dump()
    }


# ============================================================
# 測試區域
# ============================================================
if __name__ == "__main__":
    """
    測試 knowledge_search_node

    執行方式：
    python -m src.coursegen.agents.knowledge_search
    """
    import logging

    logging.basicConfig(
        level=logging.WARNING,
        format="{asctime} | {name:<20} | {levelname:<8} | {message}",
        datefmt="%Y-%m-%d %H:%M:%S",
        style="{",
    )

    logger = logging.getLogger("coursegen")  # 你的模組前綴
    logger.setLevel(logging.DEBUG)

    import os
    from dotenv import load_dotenv

    load_dotenv()

    # 模擬 State 和 Runtime
    class MockRuntime:
        class MockContext:
            model_name = "google/gemini-2.5-flash"
            base_url = os.getenv("BASE_URL")
            openrouter_api_key = os.getenv("OPENROUTER_API_KEY")
            tavily_api_key = os.getenv("TAVILY_KEY")

        context = MockContext()

    mock_state = {
        "question": "How to learn Python programming?",
        "user_preferences": "Beginner level",
    }

    result = knowledge_search_node(mock_state, MockRuntime())

    if result["knowledge_context"]:
        kc = KnowledgeContext(**result["knowledge_context"])
        print(f"✅ Search successful!")
        print(f"Query: {kc.query}")
        print(f"Results: {len(kc.results)} items")
        print(f"\nSynthesized Knowledge:\n{kc.synthesized_knowledge}")
    else:
        print("❌ No knowledge context returned")
