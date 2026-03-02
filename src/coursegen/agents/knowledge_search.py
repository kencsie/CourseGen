from coursegen.schemas import (
    RoadmapState,
    ContextSchema,
    KnowledgeContext,
    SearchResult,
    RoadmapSearchQueryResult,
    SourceFilterResponse,
)
from coursegen.prompts.knowledge_synthesis import (
    KNOWLEDGE_SYNTHESIS_PROMPT,
    ROADMAP_SOURCE_FILTER_PROMPT,
)
from coursegen.prompts.roadmap import ROADMAP_SEARCH_QUERY_PROMPT
from coursegen.utils.content_cleaner import clean_search_results, select_top_sources
from langgraph.runtime import Runtime
from langchain.chat_models import init_chat_model
from tavily import TavilyClient
import logging

logger = logging.getLogger(__name__)


def knowledge_search_node(state: RoadmapState, runtime: Runtime[ContextSchema]) -> dict:
    """
    在生成 roadmap 前，先搜尋外部知識。
    支援 multi-query、URL 去重、source filtering。
    """

    if not runtime.context.tavily_api_key:
        logger.warning("TAVILY API KEY 不存在，跳過此流程")
        return {}

    tavily_client = TavilyClient(api_key=runtime.context.tavily_api_key)

    logger.info(f"知識搜尋開始，question: {state.get('question')}")

    # ── 1. 讀歷史 ──
    previous_queries = state.get("roadmap_search_queries_history", [])
    urls_seen = set(state.get("roadmap_search_urls_seen", []))

    # ── 2. 組裝 critic feedback ──
    feedback_history = state.get("roadmap_feedback", [])
    retry_target = state.get("roadmap_retry_target", "")
    if feedback_history and retry_target == "search":
        latest_feedback = (
            feedback_history[-1]
            if isinstance(feedback_history[-1], str)
            else feedback_history[-1].get("feedback", "")
        )
        critic_feedback_str = (
            f"\n⚠️ Previous search was inadequate. Critic feedback:\n"
            f"{latest_feedback}\n"
            f"Please generate DIFFERENT search queries that address the above issues."
        )
    else:
        critic_feedback_str = ""

    # 組裝 previous queries 提示
    if previous_queries:
        flat_prev = [q for batch in previous_queries for q in batch]
        previous_queries_str = (
            f"\n⚠️ Previously used queries (do NOT repeat these):\n"
            + "\n".join(f"- {q}" for q in flat_prev)
        )
    else:
        previous_queries_str = ""

    # ── 3. LLM 生成 3 queries ──
    query_model = init_chat_model(
        model=runtime.context.model_name,
        model_provider="openai",
        api_key=runtime.context.openrouter_api_key,
        base_url=runtime.context.base_url,
        temperature=0,
    )
    query_prompt = ROADMAP_SEARCH_QUERY_PROMPT.format(
        question=state.get("question"),
        critic_feedback=critic_feedback_str,
        previous_queries=previous_queries_str,
    )
    try:
        query_chain = query_model.with_structured_output(RoadmapSearchQueryResult).with_retry(
            stop_after_attempt=3,
        )
        query_result = query_chain.invoke(query_prompt)
        queries = [q.strip() for q in query_result.queries]
        topic_keyword = query_result.topic_keyword.strip()
        logger.info(f"topic_keyword: {topic_keyword}")
        logger.info(f"搜尋 reasoning: {query_result.reasoning[:100]}...")
        logger.info(f"生成 {len(queries)} 個 queries: {queries}")
    except Exception as e:
        logger.warning(f"Query 生成重試 3 次仍失敗: {e}")
        return {
            "roadmap_search_queries_history": previous_queries,
            "roadmap_search_urls_seen": list(urls_seen),
        }

    # ── 4. 每個 query 做 Tavily search，合併 + URL 去重 ──
    all_results: list[SearchResult] = []
    new_urls: set[str] = set()
    tavily_answers: list[str] = []

    for q in queries:
        try:
            response = tavily_client.search(
                query=q,
                search_depth="advanced",
                include_answer="advanced",
                include_raw_content="markdown",
                exclude_domains=["youtube.com"],
            )
        except Exception as e:
            logger.warning(f"Tavily search failed for query '{q}': {e}")
            continue

        answer = response.get("answer", "")
        if answer:
            tavily_answers.append(answer)
            logger.info(f"Tavily answer for '{q}': {len(answer)} 字")

        for result in response.get("results", []):
            url = result["url"]
            if url in urls_seen or url in new_urls:
                continue
            new_urls.add(url)
            all_results.append(
                SearchResult(
                    title=result["title"],
                    url=url,
                    content=result["content"],
                    score=result["score"],
                    raw_content=result.get("raw_content") or None,
                )
            )

    logger.info(f"Tavily 搜尋完成，取得 {len(all_results)} 筆不重複結果")

    if not all_results:
        logger.warning("搜尋無結果，跳過 source filtering")
        return {
            "roadmap_search_queries_history": previous_queries + [queries],
            "roadmap_search_urls_seen": list(urls_seen | new_urls),
        }

    # ── 5. LLM source filtering ──
    filter_formatted = "\n\n".join(
        f"=== 來源 {i + 1}: {r.title} ===\nURL: {r.url}\n{r.content}"
        for i, r in enumerate(all_results)
    )

    filter_model = init_chat_model(
        model=runtime.context.model_name,
        model_provider="openai",
        api_key=runtime.context.openrouter_api_key,
        base_url=runtime.context.base_url,
        temperature=0,
    )
    filter_prompt = ROADMAP_SOURCE_FILTER_PROMPT.format(
        topic=state.get("question"),
        search_results=filter_formatted,
    )
    try:
        filter_chain = filter_model.with_structured_output(SourceFilterResponse).with_retry(
            stop_after_attempt=3,
        )
        filter_result = filter_chain.invoke(filter_prompt)
        kept_indices = {s.index for s in filter_result.results if s.score >= 8}
        if not kept_indices:
            logger.info("無 >= 8 分來源，fallback 至 >= 6 分門檻")
            kept_indices = {s.index for s in filter_result.results if s.score >= 6}
        filtered_results = [r for i, r in enumerate(all_results) if (i + 1) in kept_indices]
        logger.info(f"Source filtering 保留 {len(filtered_results)}/{len(all_results)} 個來源")
    except Exception as e:
        logger.warning(f"Source filtering 重試 3 次仍失敗，使用空結果: {e}")
        filtered_results = []

    # ── 5.3. Top-K source selection ──
    if len(filtered_results) > 4 and runtime.context.cheap_model:
        filtered_results = select_top_sources(
            results=filtered_results,
            topic=state.get("question"),
            node_label=state.get("question"),
            model_name=runtime.context.cheap_model,
            api_key=runtime.context.openrouter_api_key,
            base_url=runtime.context.base_url,
            max_sources=4,
            config={"run_name": "roadmap_source_selection"},
        )

    # ── 5.5. Cheap LLM raw_content cleaning ──
    if filtered_results and runtime.context.cheap_model:
        filtered_results = clean_search_results(
            results=filtered_results,
            topic=state.get("question"),
            node_label=state.get("question"),
            model_name=runtime.context.cheap_model,
            api_key=runtime.context.openrouter_api_key,
            base_url=runtime.context.base_url,
            config={"run_name": "roadmap_content_cleaning"},
        )

    if not filtered_results:
        logger.warning("過濾後無結果，跳過 knowledge synthesis")
        return {
            "roadmap_search_queries_history": previous_queries + [queries],
            "roadmap_search_urls_seen": list(urls_seen | new_urls),
        }

    # ── 6. Knowledge synthesis ──
    synthesis_formatted = "\n\n".join(
        f"=== 來源 {i + 1}: {r.title} ===\nURL: {r.url}\n{r.raw_content or r.content}"
        for i, r in enumerate(filtered_results)
    )

    synthesis_model = init_chat_model(
        model=runtime.context.model_name,
        model_provider="openai",
        api_key=runtime.context.openrouter_api_key,
        base_url=runtime.context.base_url,
        temperature=0.1,
    )

    answers_formatted = "\n\n".join(
        f"=== Tavily 整合摘要 {i + 1} ===\n{a}"
        for i, a in enumerate(tavily_answers)
    ) if tavily_answers else "（無）"

    logger.info("LLM 統整知識中...")

    try:
        response = synthesis_model.with_retry(stop_after_attempt=3).invoke(
            KNOWLEDGE_SYNTHESIS_PROMPT.format(
                question=state.get("question"),
                search_results=synthesis_formatted,
                tavily_answers=answers_formatted,
            )
        )
        synthesized = str(response.content)
    except Exception as e:
        logger.warning(f"Knowledge synthesis 重試 3 次仍失敗: {e}")
        synthesized = ""
    logger.info(f"知識統整完成，長度: {len(synthesized)} 字")

    # ── 7. 回傳結果 + 搜尋歷史更新 ──
    return {
        "topic_keyword": topic_keyword,
        "knowledge_context": KnowledgeContext(
            query=state.get("question"),
            results=filtered_results,
            synthesized_knowledge=synthesized,
        ).model_dump(),
        "roadmap_search_queries_history": previous_queries + [queries],
        "roadmap_search_urls_seen": list(urls_seen | new_urls),
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

    logger = logging.getLogger("coursegen")
    logger.setLevel(logging.DEBUG)

    import os
    from dotenv import load_dotenv

    load_dotenv()

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

    if result.get("knowledge_context"):
        kc = KnowledgeContext(**result["knowledge_context"])
        print(f"Search successful!")
        print(f"Query: {kc.query}")
        print(f"Results: {len(kc.results)} items")
        print(f"\nSynthesized Knowledge:\n{kc.synthesized_knowledge}")
        print(f"\nQueries history: {result.get('roadmap_search_queries_history')}")
        print(f"URLs seen: {len(result.get('roadmap_search_urls_seen', []))}")
    else:
        print("No knowledge context returned")
