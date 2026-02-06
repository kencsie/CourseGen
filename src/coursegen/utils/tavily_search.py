import os
from tavily import TavilyClient
from coursegen.schemas import State, ContextSchema, SearchResult, KnowledgeContext
from langchain.chat_models import init_chat_model
from langgraph.runtime import Runtime


def create_search_query(question: str, user_preferences: str) -> str:
    """從使用者問題創建優化的搜尋查詢"""
    # 提取核心主題（去除 "How to learn" 等常見前綴）
    query = question.lower()
    query = query.replace("how to learn", "")
    query = query.replace("how to", "")
    query = query.replace("learn", "")
    query = query.strip()

    # 添加 "tutorial" 或 "guide" 關鍵詞以獲得更好的學習資源
    return f"{query} tutorial guide 2024 2025 2026"


def synthesize_search_results(question: str, results: list, api_key: str, base_url: str) -> str:
    """用 LLM 將搜尋結果整合成關鍵發現"""
    if not results:
        return "未找到相關的外部資源。"

    # 準備搜尋結果的文字
    results_text = "\n\n".join([
        f"【來源 {i+1}】{r['title']}\nURL: {r['url']}\n內容: {r['content'][:500]}..."
        for i, r in enumerate(results[:5])
    ])

    prompt = f"""
你是一位學習資源分析專家。請基於以下搜尋結果，為主題「{question}」提煉出3-5個關鍵發現（Key Findings）。

搜尋結果：
{results_text}

請以條列式輸出：
1. 最重要的學習資源或工具
2. 當前最佳實務或推薦方法
3. 需要避免的過時做法或常見陷阱
4. 學習路徑的推薦順序（如果有）
5. 其他重要發現

重點：
- 只基於搜尋結果中的真實資訊
- 不要編造不存在的內容
- 突出最新的、2024-2026年的資訊
"""

    model = init_chat_model(
        model="openai/gpt-4o-mini",  # 使用較便宜的模型進行總結
        model_provider="openai",
        api_key=api_key,
        base_url=base_url,
        temperature=0.3
    )

    try:
        response = model.invoke(prompt)
        return response.content
    except Exception as e:
        print(f"⚠️  搜尋結果整合失敗: {e}")
        return "無法整合搜尋結果，將使用原始搜尋結果。"


def knowledge_search_node(state: State, runtime: Runtime[ContextSchema]) -> dict:
    """LangGraph node - 執行搜尋並整合結果"""
    # 如果已經執行過搜尋，直接跳過
    if state.get("search_performed"):
        return {"search_performed": True}

    try:
        tavily_key = os.getenv("TAVILY_KEY")
        if not tavily_key:
            print("⚠️  未設定 TAVILY_KEY，跳過知識搜尋")
            return {
                "search_performed": True,
                "knowledge_context": None
            }

        client = TavilyClient(tavily_key)

        # 創建優化的搜尋查詢
        query = create_search_query(state["question"], state["user_preferences"])
        print(f"🔍 搜尋查詢: {query}")

        # 執行搜尋
        response = client.search(
            query=query,
            search_depth="advanced",
            max_results=5,
        )

        # 整合搜尋結果
        summary = synthesize_search_results(
            state["question"],
            response.get("results", []),
            runtime.context.openrouter_api_key,
            runtime.context.base_url
        )

        # 構建 SearchResult 列表
        search_results = []
        for r in response.get("results", [])[:5]:
            search_results.append(SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                content=r.get("content", "")[:500],  # 截斷以節省 token
                score=r.get("score", 0.0)
            ))

        knowledge_context = KnowledgeContext(
            query=query,
            results=search_results,
            summary=summary
        )

        print(f"✅ 找到 {len(search_results)} 個相關資源")

        return {
            "knowledge_context": knowledge_context.model_dump(),
            "search_performed": True
        }

    except Exception as e:
        print(f"⚠️  搜尋失敗: {e}，繼續使用 LLM 內部知識")
        return {
            "search_performed": True,
            "knowledge_context": None
        }


def search_node(state: State):
    """舊版搜尋節點（向後兼容）"""
    client = TavilyClient(os.getenv("TAVILY_KEY"))
    response = client.search(
        query=str(state["messages"][-1].content),
        search_depth="advanced",
        include_usage=True,
        include_raw_content="markdown",
    )
    return {"retrieved_doc": response["results"]}
